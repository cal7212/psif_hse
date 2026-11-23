# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Work permits: Confined Space Permit (29 CFR 1910.146) and Energized Electrical Work Permit
(NFPA 70E 130.2(B)).

A permit is drafted, then issued (approved) by submitting it, and closed from the form when the
work is done, a prohibited condition arises or the authorized period runs out. Closing does not
cancel: the closed permit is the record that is kept (1910.146(e)(6): at least one year)."""

import frappe
from frappe import _
from frappe.utils import cstr, get_datetime, now_datetime

from hse.training_matrix.status import NOT_APPLICABLE

CLOSED = "Closed"
CLOSURE_REASONS = ("Work Completed", "Prohibited Condition", "Permit Expired")
# doctype: (start field, end field, status while the work is authorized)
PERMITS = {
	"Confined Space Permit": ("permit_start", "permit_end", "Issued"),
	"Energized Electrical Work Permit": ("work_start", "work_end", "Approved"),
}


def has_text(value) -> bool:
	return bool(cstr(value).strip())


def window_errors(doc, start_field: str, end_field: str, issuing: bool = False) -> list[str]:
	"""The authorized period must end after it starts and, when issuing, not be over already."""
	start, end = doc.get(start_field), doc.get(end_field)
	if not start or not end:
		return []
	errors = []
	if get_datetime(end) <= get_datetime(start):
		errors.append(
			_("{0} must be after {1}.").format(
				_(doc.meta.get_label(end_field)), _(doc.meta.get_label(start_field))
			)
		)
	elif issuing and get_datetime(end) <= now_datetime():
		errors.append(
			_("The authorized period is already over. Set a new {0}.").format(
				_(doc.meta.get_label(end_field))
			)
		)
	return errors


def workers_with_role(workers, role: str) -> list:
	return [w for w in workers if w.role == role]


def same_person(a, b) -> bool:
	if a.employee and b.employee:
		return a.employee == b.employee
	return cstr(a.worker_name).strip().lower() == cstr(b.worker_name).strip().lower()


def unqualified(employees, course_keyword: str) -> list[str]:
	"""Employees whose training matrix does not show them Qualified on any course whose title
	contains course_keyword (e.g. "70E"). Empty when no such course is set up, so sites without
	the course are not nagged."""
	employees = [e for e in dict.fromkeys(employees) if e]
	if not employees or not frappe.db.exists("DocType", "Employee Training Matrix Item"):
		return []
	courses = frappe.get_all(
		"Training Requirement", filters={"course_title": ["like", f"%{course_keyword}%"]}, pluck="name"
	)
	if not courses:
		return []
	matrices = frappe.get_all(
		"Employee Training Matrix",
		filters={"employee": ["in", employees]},
		fields=["name", "employee"],
	)
	qualified_matrices = set(
		frappe.get_all(
			"Employee Training Matrix Item",
			filters={
				"parenttype": "Employee Training Matrix",
				"parent": ["in", [m.name for m in matrices] or [""]],
				"training_requirement": ["in", courses],
				"qualification": "Qualified",
				"status": ["!=", NOT_APPLICABLE],
			},
			pluck="parent",
		)
	)
	qualified = {m.employee for m in matrices if m.name in qualified_matrices}
	return [e for e in employees if e not in qualified]


def warn_unqualified(doc, course_keyword: str, roles: tuple[str, ...], course_label: str):
	"""A warning, not a block: contractors have no training matrix, and their qualification is
	checked another way."""
	employees = [w.employee for w in doc.workers if w.employee and (not roles or w.role in roles)]
	missing = unqualified(employees, course_keyword)
	if missing:
		names = [w.worker_name or w.employee for w in doc.workers if w.employee in missing]
		frappe.msgprint(
			_(
				"Not shown as qualified for {0} on the training matrix: {1}. Check their qualification before work starts."
			).format(course_label, ", ".join(dict.fromkeys(names))),
			title=_("Training"),
			indicator="orange",
		)


def user_has_any_role(roles) -> bool:
	return bool(set(roles) & set(frappe.get_roles()))


@frappe.whitelist()
def close_permit(doctype: str, name: str, reason: str, notes: str | None = None) -> str:
	"""Close an issued permit. Entrants still signed in are signed out at the closing time."""
	if doctype not in PERMITS:
		frappe.throw(_("{0} is not a work permit.").format(doctype))
	if reason not in CLOSURE_REASONS:
		frappe.throw(_("Choose why the permit is being closed."))
	if reason == "Prohibited Condition" and not has_text(notes):
		frappe.throw(_("Describe the prohibited condition in the closure notes."))
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("write")
	_start, _end, open_status = PERMITS[doctype]
	if doc.docstatus != 1 or doc.status != open_status:
		frappe.throw(_("Only an {0} permit can be closed.").format(_(open_status).lower()))
	closed_at = now_datetime()
	doc.update(
		{
			"status": CLOSED,
			"closure_reason": reason,
			"closure_notes": notes,
			"closed_by": frappe.session.user,
			"closed_on": closed_at,
		}
	)
	for w in doc.get("workers") or []:
		if w.time_in and not w.time_out:
			w.time_out = closed_at
	doc.save()
	return doc.status
