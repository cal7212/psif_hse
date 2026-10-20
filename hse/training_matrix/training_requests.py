# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""TRN-703 Training Requests (TRN-700 Rev 1 §4.12).

The employee requests training from My Training; their manager approves or rejects it based on
the benefit to PSIF. Approved requests go to the Training Coordinator to arrange. For external
training, the employee marks it completed and the certificate is due to the Training Coordinator
within Settings → Certificate Due business days (10); a reminder goes out if it is late.
"""

import frappe
from frappe import _
from frappe.utils import add_days, get_url, getdate, today

from hse.training_matrix.notifications import _assign, settings, users_with_roles
from hse.training_matrix.skills import is_manager_of, manager_users

REQUEST = "Training Request"
COORDINATOR = "Training Coordinator"


def add_business_days(start, days: int):
	d = getdate(start)
	while days > 0:
		d = getdate(add_days(d, 1))
		if d.weekday() < 5:
			days -= 1
	return d


def own_employee() -> str | None:
	return frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")


def _notify(users, subject, message, request):
	users = [u for u in users if u]
	if users:
		frappe.sendmail(
			recipients=users,
			subject=subject,
			message=message,
			reference_doctype=REQUEST,
			reference_name=request,
		)


@frappe.whitelist()
def create_training_request(
	request_type: str,
	training_title: str,
	reason: str,
	training_requirement: str | None = None,
	provider: str | None = None,
	preferred_date: str | None = None,
	estimated_cost: float | None = None,
) -> str:
	employee = own_employee()
	if not employee:
		frappe.throw(_("Your login is not linked to an active employee."), frappe.PermissionError)
	doc = frappe.get_doc(
		{
			"doctype": REQUEST,
			"employee": employee,
			"request_type": request_type,
			"training_title": training_title,
			"training_requirement": training_requirement or None,
			"provider": provider,
			"preferred_date": preferred_date or None,
			"estimated_cost": estimated_cost or None,
			"reason": reason,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	_assign(
		manager_users(employee),
		REQUEST,
		doc.name,
		_("{0} requests training: {1}. Approve or reject it (TRN-703).").format(
			doc.employee_name, doc.training_title
		),
	)
	return doc.name


@frappe.whitelist()
def decide_training_request(name: str, decision: str, notes: str | None = None) -> None:
	doc = frappe.get_doc(REQUEST, name)
	if decision not in ("Approved", "Rejected"):
		frappe.throw(_("Decision must be Approved or Rejected."))
	if doc.employee == own_employee() or not is_manager_of(doc.employee):
		frappe.throw(
			_("Only the employee's manager, HR or the Training Coordinator can decide."),
			frappe.PermissionError,
		)
	if doc.status != "Pending":
		frappe.throw(_("This request has already been decided."))
	doc.update(
		{
			"status": decision,
			"decided_by": frappe.session.user,
			"decided_on": today(),
			"decision_notes": notes,
		}
	)
	doc.flags.ignore_permissions = True
	doc.save()
	user = frappe.db.get_value("Employee", doc.employee, "user_id")
	_notify(
		[user],
		_("Your training request was {0}: {1}").format(_(decision).lower(), doc.training_title),
		_("<p>{0}</p><p>{1}</p><p>See <a href='{2}'>My Training</a>.</p>").format(
			frappe.utils.escape_html(doc.training_title),
			frappe.utils.escape_html(notes or ""),
			get_url("/my-training"),
		),
		doc.name,
	)
	if decision == "Approved":
		_assign(
			sorted(users_with_roles([COORDINATOR])),
			REQUEST,
			doc.name,
			_("Approved training request for {0}: {1}. Arrange the training.").format(
				doc.employee_name, doc.training_title
			),
		)


@frappe.whitelist()
def complete_training_request(name: str, completed_on: str) -> None:
	doc = frappe.get_doc(REQUEST, name)
	if doc.employee != own_employee() and not is_manager_of(doc.employee):
		frappe.throw(_("Only the employee or their manager can mark this completed."), frappe.PermissionError)
	if doc.status != "Approved":
		frappe.throw(_("Only approved requests can be marked completed."))
	if getdate(completed_on) > getdate(today()):
		frappe.throw(_("The completion date cannot be in the future."))
	doc.status, doc.completed_on = "Completed", completed_on
	if doc.request_type == "External Training":
		doc.certificate_due = add_business_days(completed_on, settings().certificate_business_days or 10)
	doc.flags.ignore_permissions = True
	doc.save()
	if doc.request_type == "External Training":
		_assign(
			sorted(users_with_roles([COORDINATOR])),
			REQUEST,
			doc.name,
			_(
				"Collect {0}'s certificate for {1} by {2} and record it as an External Certificate training record."
			).format(doc.employee_name, doc.training_title, frappe.format(doc.certificate_due, "Date")),
		)


def remind_overdue_certificates(on_date=None) -> None:
	"""Daily: one reminder to the employee and manager when an external certificate is late."""
	on_date = getdate(on_date or today())
	for r in frappe.get_all(
		REQUEST,
		filters={
			"status": "Completed",
			"request_type": "External Training",
			"training_record": ["is", "not set"],
			"certificate_due": ["<", on_date],
			"certificate_reminded_on": ["is", "not set"],
		},
		fields=["name", "employee", "employee_name", "training_title", "certificate_due"],
	):
		user = frappe.db.get_value("Employee", r.employee, "user_id")
		_notify(
			[user, *manager_users(r.employee)],
			_("Training certificate overdue: {0}").format(r.training_title),
			_(
				"<p>The certificate for {0} ({1}) was due on {2}. Please send it to the Training Coordinator.</p>"
			).format(
				frappe.utils.escape_html(r.training_title),
				frappe.utils.escape_html(r.employee_name),
				frappe.format(r.certificate_due, "Date"),
			),
			r.name,
		)
		frappe.db.set_value(REQUEST, r.name, "certificate_reminded_on", on_date, update_modified=False)


def my_requests(employee: str) -> list[dict]:
	return frappe.get_all(
		REQUEST,
		filters={"employee": employee},
		fields=[
			"name",
			"training_title",
			"request_type",
			"status",
			"preferred_date",
			"decision_notes",
			"certificate_due",
		],
		order_by="creation desc",
		limit=20,
	)
