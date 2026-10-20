# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""My Training: the employee's own matrix and acknowledgments in the Learning portal (/my-training)."""

import frappe
from frappe import _
from frappe.utils import now_datetime

from hse.training_matrix import status as st
from hse.training_matrix.evidence import acknowledgment_required, recalculate

SHOWN = (st.OVERDUE, st.DUE, st.IN_PROGRESS, st.NOT_STARTED, st.COMPLETED, st.CONFIRM)


def own_employee() -> str | None:
	if frappe.session.user == "Guest":
		return None
	return frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")


def pending_acknowledgments(employee: str) -> list[dict]:
	rows = frappe.get_all(
		"Training Record Attendee",
		filters={"employee": employee, "parenttype": "Training Record", "acknowledged": 0},
		fields=["parent"],
	)
	if not rows:
		return []
	records = frappe.get_all(
		"Training Record",
		filters={"name": ["in", [r.parent for r in rows]], "docstatus": 1},
		fields=[
			"name",
			"training_requirement",
			"course_title",
			"training_date",
			"trainer_name",
			"external_provider",
			"source",
		],
		order_by="training_date desc",
	)
	return [r for r in records if acknowledgment_required(r.source)]


def my_training_context(employee: str) -> dict:
	matrix = (
		frappe.get_doc("Employee Training Matrix", employee)
		if frappe.db.exists("Employee Training Matrix", employee)
		else None
	)
	rows = [r for r in (matrix.items if matrix else []) if r.status in SHOWN]
	order = {s: i for i, s in enumerate(SHOWN)}
	rows.sort(key=lambda r: (order.get(r.status, 9), str(r.due_date or "9999"), r.training_requirement))
	courses = {}
	if frappe.get_meta("Training Requirement").has_field("lms_course"):
		courses = {
			r.name: r.lms_course
			for r in frappe.get_all(
				"Training Requirement",
				filters={"name": ["in", [r.training_requirement for r in rows] or [""]]},
				fields=["name", "lms_course"],
			)
		}
	from hse.training_matrix.training_requests import my_requests

	return {
		"requests": my_requests(employee),
		"request_courses": frappe.get_all(
			"Training Requirement",
			filters={"disabled": 0},
			fields=["name", "course_title"],
			order_by="name asc",
		),
		"matrix": matrix,
		"skills": [
			s for s in (matrix.skills if matrix else []) if s.needed_for != "Held" or s.status == "Authorized"
		],
		"rows": rows,
		"courses": courses,
		"pending": pending_acknowledgments(employee),
		"records": frappe.get_all(
			"Training Record",
			filters={
				"name": [
					"in",
					frappe.get_all(
						"Training Record Attendee",
						filters={"employee": employee, "parenttype": "Training Record"},
						pluck="parent",
					)
					or [""],
				],
				"docstatus": 1,
			},
			fields=["name", "training_requirement", "course_title", "training_date", "source"],
			order_by="training_date desc",
			limit=20,
		),
	}


@frappe.whitelist()
def acknowledge_training(record: str) -> None:
	"""The trainee confirms attendance and understanding under their own login (TRN-700 §4.1)."""
	employee = own_employee()
	if not employee:
		frappe.throw(_("Your login is not linked to an active employee."), frappe.PermissionError)
	doc = frappe.get_doc("Training Record", record)
	if doc.docstatus != 1:
		frappe.throw(_("This training record has not been submitted yet."))
	row = next((a for a in doc.attendees if a.employee == employee), None)
	if not row:
		frappe.throw(_("You are not listed on this training record."), frappe.PermissionError)
	if row.acknowledged:
		return
	row.db_set({"acknowledged": 1, "acknowledged_on": now_datetime()}, update_modified=False)
	doc.reload()
	doc.db_set("status", doc.get_status(), update_modified=False)
	recalculate(employee, doc.training_requirement)
