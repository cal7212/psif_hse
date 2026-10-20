# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Import LMS History: LMS Certificates issued before the Training Matrix existed.

The live Frappe Learning integration only creates training records when something happens
(an enrollment reaching 100%, a quiz, a new certificate). Certificates issued earlier never
counted. This one-time, repeatable import turns each certificate held by an active employee,
for a course linked to a Training Requirement, into a submitted TRN-702 record:

- dated the certificate's issue date, with its expiry date;
- only when the employee's best quiz scores meet the pass mark (80% for quiz-verified courses);
- marked "Imported from LMS certificate ..." with the document revision "unknown (imported)",
  because the revision trained on back then is not known;
- never twice for the same certificate and course, and not when a live LMS record already
  covers the same pass.

Old certificates on annual courses correctly show as Overdue; courses verified by a practical
evaluation stay In Progress until a TRN-704 evaluation is submitted.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate

from hse.training_matrix import lms
from hse.training_matrix.matrix import MANAGE_ROLES

WILL_IMPORT = "Will import"
ALREADY = "Already recorded"
BELOW_PASS = "Quiz below pass mark"
NO_MATRIX = "No training matrix"
IMPORTED_REVISION = "unknown (imported)"


def classify(has_matrix: bool, already: bool, passed: bool) -> str:
	if not has_matrix:
		return NO_MATRIX
	if already:
		return ALREADY
	return WILL_IMPORT if passed else BELOW_PASS


def candidates() -> list[dict]:
	"""Every (certificate, course) pair, with what the import would do and why."""
	if not lms.installed() or not frappe.get_meta("Training Requirement").has_field("lms_course"):
		return []
	requirements: dict[str, list] = {}
	for r in frappe.get_all(
		"Training Requirement",
		filters={"disabled": 0, "lms_course": ["is", "set"]},
		fields=["name", "lms_course", "verification_method"],
	):
		requirements.setdefault(r.lms_course, []).append(r)
	if not requirements:
		return []
	rows = []
	for cert in frappe.get_all(
		"LMS Certificate",
		filters={"course": ["in", list(requirements)]},
		fields=["name", "member", "course", "issue_date", "expiry_date"],
		order_by="issue_date asc",
	):
		employee = lms.employee_for_user(cert.member)
		if not employee:
			continue  # not an active employee: nothing to put on a matrix
		employee_name = frappe.db.get_value("Employee", employee, "employee_name")
		has_matrix = bool(frappe.db.exists("Employee Training Matrix", employee))
		scores = lms.best_scores(cert.member, cert.course)
		for req in requirements[cert.course]:
			rows.append(
				frappe._dict(
					certificate=cert.name,
					member=cert.member,
					course=cert.course,
					issue_date=cert.issue_date,
					expiry_date=cert.expiry_date,
					employee=employee,
					employee_name=employee_name,
					training_requirement=req.name,
					score=min((best for best, _mark in scores.values()), default=None),
					action=classify(
						has_matrix,
						already_imported(employee, req.name, cert),
						lms.passes(scores, req.verification_method),
					),
				)
			)
	return rows


def already_imported(employee: str, requirement: str, cert) -> bool:
	"""This certificate was imported before, or a live LMS record covers the same pass."""
	parents = frappe.get_all(
		"Training Record Attendee",
		filters={"employee": employee, "parenttype": "Training Record"},
		pluck="parent",
	)
	if not parents:
		return False
	return bool(
		frappe.db.exists(
			"Training Record",
			{
				"name": ["in", parents],
				"docstatus": 1,
				"training_requirement": requirement,
				"imported_from": cert.name,
			},
		)
		or frappe.db.exists(
			"Training Record",
			{
				"name": ["in", parents],
				"docstatus": 1,
				"training_requirement": requirement,
				"source": "LMS Course",
				"training_date": [">=", cert.issue_date],
			},
		)
	)


def create_record(row) -> str:
	record = frappe.get_doc(
		{
			"doctype": "Training Record",
			"training_requirement": row.training_requirement,
			"training_date": row.issue_date,
			"source": "LMS Course",
			"lms_course": row.course,
			"imported_from": row.certificate,
			"document_revision": IMPORTED_REVISION,
			"topics": _("Imported from LMS certificate {0}").format(row.certificate),
			"attendees": [
				{
					"employee": row.employee,
					"score": row.score,
					"result": "Pass",
					"acknowledged": 1,
					"acknowledged_on": get_datetime(row.issue_date),
					"expires_on": row.expiry_date,
				}
			],
		}
	)
	record.flags.ignore_permissions = True
	record.insert()
	record.submit()
	return record.name


@frappe.whitelist()
def preview_lms_history() -> dict:
	frappe.only_for(MANAGE_ROLES)
	rows = candidates()
	counts: dict[str, int] = {}
	for r in rows:
		counts[r.action] = counts.get(r.action, 0) + 1
	return {
		"counts": counts,
		"rows": [
			{
				"employee_name": r.employee_name,
				"training_requirement": r.training_requirement,
				"certificate": r.certificate,
				"issue_date": str(getdate(r.issue_date)) if r.issue_date else None,
				"expiry_date": str(getdate(r.expiry_date)) if r.expiry_date else None,
				"score": r.score,
				"action": r.action,
			}
			for r in rows
		],
	}


@frappe.whitelist()
def import_lms_history() -> dict:
	frappe.only_for(MANAGE_ROLES)
	created, failed = [], []
	for row in candidates():
		if row.action != WILL_IMPORT:
			continue
		frappe.db.savepoint("hse_lms_history")
		try:
			created.append(create_record(row))
		except Exception:
			frappe.db.rollback(save_point="hse_lms_history")
			frappe.log_error(title=_("LMS history import failed for {0}").format(row.certificate))
			failed.append(row.certificate)
	frappe.msgprint(
		_("Imported {0} training record(s) from LMS certificates.").format(len(created))
		+ (" " + _("{0} failed; see the Error Log.").format(len(failed)) if failed else "")
	)
	return {"created": created, "failed": failed}
