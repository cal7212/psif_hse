# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Frappe Learning (LMS) integration, active only when the lms app is installed.

- A Training Requirement can name an LMS Course. Employees who need the course are enrolled
  automatically, so it appears in their Learning portal.
- When an enrollment reaches 100% and every quiz in the course has a passing attempt, a TRN-702
  Training Record is created and submitted under the employee's completion. Quiz-verified
  courses need 80% (TRN-700 Rev 1 Appendix A); others use the quiz's own pass mark.
- An LMS Certificate's expiry date is copied to that record, for courses renewed per certificate.
- When a refresher falls due, the course is reopened (lesson progress cleared) so the employee
  takes it again. The earlier Training Record keeps the history.

Built against Frappe Learning 2.66. Errors here are logged, never raised into the Learning
portal, so a lesson save never fails because of this module.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime, today

from hse.training_matrix import status as st
from hse.training_matrix.evidence import QUIZ_METHODS, QUIZ_PASS_MARK

COMPLETE = 100
SIDEBAR_ROUTE = "my-training"


def installed() -> bool:
	return "lms" in frappe.get_installed_apps()


# ---------------------------------------------------------------- setup
def setup():
	"""Custom field on Training Requirement and the My Training sidebar link (run on migrate)."""
	if not installed():
		return
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Training Requirement": [
				{
					"fieldname": "lms_course",
					"fieldtype": "Link",
					"label": "LMS Course",
					"options": "LMS Course",
					"insert_after": "verification_method",
					"module": "Training Matrix",
					"description": "Employees who need this course are enrolled automatically; completing it creates a TRN-702 record.",
				}
			]
		},
		update=True,
	)
	add_sidebar_link()


def add_sidebar_link():
	settings = frappe.get_single("LMS Settings")
	if any(row.route == SIDEBAR_ROUTE for row in settings.get("sidebar_items") or []):
		return
	settings.append(
		"sidebar_items", {"title": "My Training", "route": SIDEBAR_ROUTE, "icon": "graduation-cap"}
	)
	settings.flags.ignore_permissions = True
	settings.flags.ignore_mandatory = True
	settings.save()


def requirements_for_course(course: str) -> list[dict]:
	if not frappe.get_meta("Training Requirement").has_field("lms_course"):
		return []
	return frappe.get_all(
		"Training Requirement",
		filters={"lms_course": course, "disabled": 0},
		fields=["name", "verification_method", "refresher_frequency"],
	)


def employee_for_user(user: str) -> str | None:
	return frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")


# ---------------------------------------------------------------- doc events (LMS doctypes)
def enrollment_on_update(doc, method=None):
	if flt(doc.progress) >= COMPLETE:
		_safely(complete_course, doc.member, doc.course, doc.name)


def quiz_submission_on_update(doc, method=None):
	if not doc.course:
		return
	enrollment = frappe.db.get_value(
		"LMS Enrollment", {"member": doc.member, "course": doc.course}, ["name", "progress"], as_dict=True
	)
	if enrollment and flt(enrollment.progress) >= COMPLETE:
		_safely(complete_course, doc.member, doc.course, enrollment.name)


def certificate_on_update(doc, method=None):
	if doc.course and doc.expiry_date:
		_safely(apply_certificate_expiry, doc.member, doc.course, doc.expiry_date)


def _safely(fn, *args):
	savepoint = "hse_training_lms"
	frappe.db.savepoint(savepoint)
	try:
		fn(*args)
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		frappe.log_error(title=_("Training Matrix: LMS sync failed"), reference_doctype="LMS Course")


# ---------------------------------------------------------------- completion
def best_scores(member: str, course: str) -> dict[str, tuple[float, float]]:
	"""{quiz: (best percentage, quiz pass mark)} for every quiz in the course."""
	quizzes = frappe.get_all("LMS Quiz", filters={"course": course}, fields=["name", "passing_percentage"])
	scores = {}
	for q in quizzes:
		best = frappe.get_all(
			"LMS Quiz Submission",
			filters={"member": member, "quiz": q.name},
			fields=["percentage"],
			order_by="percentage desc",
			limit=1,
		)
		scores[q.name] = (flt(best[0].percentage) if best else 0.0, flt(q.passing_percentage))
	return scores


def passes(scores: dict[str, tuple[float, float]], verification: str | None) -> bool:
	for best, pass_mark in scores.values():
		mark = max(pass_mark, QUIZ_PASS_MARK) if verification in QUIZ_METHODS else pass_mark
		if best < mark:
			return False
	return True


def complete_course(member: str, course: str, enrollment: str) -> list[str]:
	employee = employee_for_user(member)
	if not employee or not frappe.db.exists("Employee Training Matrix", employee):
		return []
	scores = best_scores(member, course)
	created = []
	for req in requirements_for_course(course):
		if not passes(scores, req.verification_method):
			continue
		if already_recorded(employee, req.name, enrollment):
			continue
		created.append(create_lms_record(employee, member, req.name, course, enrollment, scores))
	return created


def already_recorded(employee: str, requirement: str, enrollment: str) -> bool:
	"""One record per pass through the course: since the course was last reopened for a refresher."""
	reopened = frappe.db.get_value(
		"Employee Training Matrix Item",
		{"parent": employee, "parenttype": "Employee Training Matrix", "training_requirement": requirement},
		"lms_reset_on",
	)
	attendee_parents = frappe.get_all(
		"Training Record Attendee",
		filters={"employee": employee, "lms_enrollment": enrollment, "parenttype": "Training Record"},
		pluck="parent",
	)
	if not attendee_parents:
		return False
	filters = {
		"name": ["in", attendee_parents],
		"docstatus": 1,
		"training_requirement": requirement,
		"source": "LMS Course",
	}
	if reopened:
		filters["training_date"] = [">=", reopened]
	return bool(frappe.db.exists("Training Record", filters))


def create_lms_record(employee, member, requirement, course, enrollment, scores) -> str:
	score = min((best for best, _mark in scores.values()), default=None)
	record = frappe.get_doc(
		{
			"doctype": "Training Record",
			"training_requirement": requirement,
			"training_date": today(),
			"source": "LMS Course",
			"lms_course": course,
			"topics": frappe.db.get_value("LMS Course", course, "title"),
			"attendees": [
				{
					"employee": employee,
					"score": score,
					"result": "Pass",
					"acknowledged": 1,
					"acknowledged_on": now_datetime(),
					"lms_enrollment": enrollment,
					"expires_on": certificate_expiry(member, course),
				}
			],
		}
	)
	record.flags.ignore_permissions = True
	record.insert()
	record.submit()
	return record.name


def certificate_expiry(member: str, course: str):
	return frappe.db.get_value(
		"LMS Certificate", {"member": member, "course": course}, "expiry_date", order_by="issue_date desc"
	)


def apply_certificate_expiry(member: str, course: str, expiry_date) -> None:
	employee = employee_for_user(member)
	if not employee:
		return
	from hse.training_matrix.evidence import recalculate

	for req in requirements_for_course(course):
		records = frappe.get_all(
			"Training Record",
			filters={
				"training_requirement": req.name,
				"source": "LMS Course",
				"lms_course": course,
				"docstatus": 1,
			},
			pluck="name",
			order_by="training_date desc",
		)
		row = (
			frappe.get_all(
				"Training Record Attendee",
				filters={"parent": ["in", records], "employee": employee, "parenttype": "Training Record"},
				fields=["name"],
				limit=1,
			)
			if records
			else []
		)
		if row:
			frappe.db.set_value("Training Record Attendee", row[0].name, "expires_on", expiry_date)
			recalculate(employee, req.name)


# ---------------------------------------------------------------- enrollment and refreshers
def enroll_required(matrix) -> None:
	"""Enroll the employee in the LMS course of every required course they are not Qualified in
	(or whose refresher is due)."""
	if not installed() or not matrix.active or not matrix.user_id:
		return
	courses = _lms_courses({r.training_requirement for r in matrix.items})
	for row in matrix.items:
		course = courses.get(row.training_requirement)
		if not course or not row.is_required:
			continue
		if row.qualification == st.QUALIFIED and row.status != st.DUE:
			continue
		_safely(ensure_enrollment, matrix.user_id, course)


def _lms_courses(requirements) -> dict[str, str]:
	if not requirements or not frappe.get_meta("Training Requirement").has_field("lms_course"):
		return {}
	return {
		r.name: r.lms_course
		for r in frappe.get_all(
			"Training Requirement",
			filters={"name": ["in", list(requirements)], "lms_course": ["is", "set"]},
			fields=["name", "lms_course"],
		)
	}


def ensure_enrollment(user: str, course: str) -> str:
	existing = frappe.db.get_value("LMS Enrollment", {"member": user, "course": course}, "name")
	if existing:
		return existing
	doc = frappe.get_doc(
		{"doctype": "LMS Enrollment", "member": user, "course": course, "member_type": "Student"}
	)
	doc.flags.ignore_permissions = True
	doc.flags.managed_by_caller = True  # created by the Training Matrix, not self-enrolment
	doc.insert()
	return doc.name


def reopen_due_refreshers(on_date=None) -> None:
	"""Daily: clear LMS lesson progress on courses whose refresher is due, so they are retaken."""
	if not installed():
		return
	on_date = getdate(on_date or today())
	rows = frappe.get_all(
		"Employee Training Matrix Item",
		filters={
			"parenttype": "Employee Training Matrix",
			"active": 1,
			"is_required": 1,
			"status": ["in", [st.DUE, st.OVERDUE]],
			"completed_on": ["is", "set"],
		},
		fields=["name", "parent", "training_requirement", "completed_on", "lms_reset_on"],
	)
	courses = _lms_courses({r.training_requirement for r in rows})
	for row in rows:
		course = courses.get(row.training_requirement)
		if not course or (row.lms_reset_on and getdate(row.lms_reset_on) > getdate(row.completed_on)):
			continue
		user = frappe.db.get_value("Employee", row.parent, "user_id")
		if user:
			_safely(reopen_course, user, course, row.name, on_date)


def reopen_course(user: str, course: str, matrix_row: str, on_date) -> None:
	enrollment = ensure_enrollment(user, course)
	frappe.db.delete("LMS Course Progress", {"member": user, "course": course})
	try:
		from lms.lms.doctype.lms_enrollment.lms_enrollment import update_enrollment

		update_enrollment(enrollment, {"progress": 0, "current_lesson": None})
	except ImportError:
		frappe.db.set_value("LMS Enrollment", enrollment, {"progress": 0, "current_lesson": None})
	frappe.db.set_value(
		"Employee Training Matrix Item", matrix_row, "lms_reset_on", on_date, update_modified=False
	)
