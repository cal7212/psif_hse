# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Retraining (TRN-700 Rev 1 §4.10).

Every trigger (incident or near miss, NCR / CAPA, audit finding, document revision, return from
absence, manager observation) is recorded as a submitted Retraining Assignment: which employees
must redo which courses, from when and by when, and why. On each listed course the employee's
matrix row gets retrain_from / retrain_due, so training completed before retrain_from no longer
counts: the row is Due until the retraining is done, and Overdue (Not Qualified) after the due date.

apply_retraining() rebuilds those fields from every submitted assignment, so submitting and
cancelling are both safe to repeat.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, getdate

from hse.training_matrix import status as st
from hse.training_matrix.evidence import needs_evaluation

ASSIGNMENT = "Retraining Assignment"
MATRIX = "Employee Training Matrix"
# Besides the employees' own manager (Reports To), these roles may assign retraining.
ASSIGNER_ROLES = ("System Manager", "HR Manager", "Training Coordinator", "Quality Manager")


def can_assign(employee: str, user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator" or set(frappe.get_roles(user)) & set(ASSIGNER_ROLES):
		return True
	manager = frappe.db.get_value("Employee", employee, "reports_to")
	return bool(manager and frappe.db.get_value("Employee", manager, "user_id") == user)


def latest_assignments(employee: str) -> dict[str, frappe._dict]:
	"""{course: the latest submitted assignment covering it} for one employee."""
	parents = frappe.get_all(
		"Retraining Assignment Employee",
		filters={"employee": employee, "parenttype": ASSIGNMENT},
		pluck="parent",
	)
	if not parents:
		return {}
	active = {
		a.name: a
		for a in frappe.get_all(
			ASSIGNMENT,
			filters={"name": ["in", parents], "docstatus": 1},
			fields=["name", "effective_date", "due_date"],
		)
	}
	latest: dict[str, frappe._dict] = {}
	for c in frappe.get_all(
		"Retraining Assignment Course",
		filters={"parent": ["in", list(active) or [""]], "parenttype": ASSIGNMENT},
		fields=["parent", "training_requirement"],
	):
		a = active[c.parent]
		key = (getdate(a.effective_date), getdate(a.due_date), a.name)
		cur = latest.get(c.training_requirement)
		if not cur or key > (getdate(cur.effective_date), getdate(cur.due_date), cur.name):
			latest[c.training_requirement] = a
	return latest


def apply_retraining(employee: str) -> None:
	if not frappe.db.exists(MATRIX, employee):
		return
	matrix = frappe.get_doc(MATRIX, employee)
	latest = latest_assignments(employee)
	rows = {r.training_requirement: r for r in matrix.items}
	for course, a in latest.items():
		row = rows.get(course)
		if not row:  # retraining on a course the role doesn't otherwise need
			row = matrix.append(
				"items",
				{
					"training_requirement": course,
					"requirement_code": st.REQUIRED,
					"assigned_on": a.effective_date,
				},
			)
		row.update(
			{"retrain_from": a.effective_date, "retrain_due": a.due_date, "retraining_assignment": a.name}
		)
	for row in matrix.items:
		if row.retraining_assignment and row.training_requirement not in latest:
			row.update({"retrain_from": None, "retrain_due": None, "retraining_assignment": None})
	matrix.flags.ignore_permissions = True
	matrix.save()
	# re-sync so retraining rows outside the role are labelled, and dropped again once closed
	from hse.training_matrix.matrix import sync_matrix

	sync_matrix(employee)


def create_assignment(
	reason_type: str,
	employees: list[str],
	courses: list[str],
	effective_date,
	due_date,
	reason: str,
	reference_doctype: str | None = None,
	reference_name: str | None = None,
	delivery: str = "As Per Course",
	notify: bool = True,
) -> str:
	doc = frappe.get_doc(
		{
			"doctype": ASSIGNMENT,
			"reason_type": reason_type,
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"effective_date": effective_date,
			"due_date": due_date,
			"delivery": delivery,
			"reason": reason,
			"employees": [{"employee": e} for e in employees],
			"courses": [{"training_requirement": c} for c in courses],
		}
	)
	doc.flags.ignore_permissions = True
	doc.flags.skip_notify = not notify
	doc.insert()
	doc.submit()
	return doc.name


# ---------------------------------------------------------------- Return from Absence
def absence_courses(employee: str) -> list[str]:
	"""High-hazard courses and courses verified by a practical evaluation that the employee needs."""
	rows = frappe.get_all(
		"Employee Training Matrix Item",
		filters={"parent": employee, "parenttype": MATRIX, "is_required": 1},
		fields=["training_requirement", "high_hazard"],
	)
	if not rows:
		return []
	verification = {
		r.name: r.verification_method
		for r in frappe.get_all(
			"Training Requirement",
			filters={"name": ["in", [r.training_requirement for r in rows]]},
			fields=["name", "verification_method"],
		)
	}
	return sorted(
		r.training_requirement
		for r in rows
		if r.high_hazard or needs_evaluation(verification.get(r.training_requirement))
	)


@frappe.whitelist()
def record_return_from_absence(
	employee: str, absence_from: str, return_date: str, extra_courses: str | list | None = None
) -> str | None:
	"""Manager or HR records a return after an extended absence (absences are not in Frappe HR)."""
	if not can_assign(employee):
		frappe.throw(_("Only the employee's manager, HR or Quality can record this."), frappe.PermissionError)
	if getdate(return_date) < getdate(absence_from):
		frappe.throw(_("The return date cannot be before the absence started."))
	settings = frappe.get_cached_doc("Training Matrix Settings")
	threshold = settings.absence_days or 90
	days = date_diff(return_date, absence_from)
	if days < threshold:
		frappe.msgprint(
			_("{0} days away is under the {1}-day threshold, so no retraining is required.").format(
				days, threshold
			)
		)
		return None
	extras = json.loads(extra_courses) if isinstance(extra_courses, str) else (extra_courses or [])
	courses = sorted(set(absence_courses(employee)) | set(extras))
	if not courses:
		frappe.msgprint(_("No high-hazard or practically evaluated courses are on this employee's matrix."))
		return None
	name = create_assignment(
		"Return from Absence",
		[employee],
		courses,
		return_date,
		add_days(return_date, settings.absence_due_days or 0),
		_("Returned on {0} after {1} days away (TRN-700 §4.10).").format(
			frappe.format(return_date, "Date"), days
		),
		reference_doctype="Employee",
		reference_name=employee,
	)
	frappe.msgprint(_("Retraining assigned for {0} course(s): {1}").format(len(courses), name))
	return name
