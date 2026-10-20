# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from hse.testing_fixtures import ensure_company, ensure_gender
from hse.training_matrix import status as st
from hse.training_matrix.matrix import sync_matrix
from hse.training_matrix.notifications import process_overdue
from hse.training_matrix.retraining import create_assignment, record_return_from_absence

DESIGNATION, ROLE = "_T Retrain Tech", "_T Retrain Role"


def ensure(doctype, name, **values):
	if not frappe.db.exists(doctype, name):
		doc = frappe.get_doc({"doctype": doctype, **values})
		doc.flags.skip_resync = True
		doc.insert()


def row(employee, course):
	return next(
		(
			r
			for r in frappe.get_doc("Employee Training Matrix", employee).items
			if r.training_requirement == course
		),
		None,
	)


class IntegrationTestRetrainingAssignment(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.setup.doctype.employee.test_employee import make_employee

		ensure("Designation", DESIGNATION, designation_name=DESIGNATION)
		ensure("Training Role", ROLE, role_name=ROLE, designations=[{"designation": DESIGNATION}])
		for course, extra in (
			("_T-RT-LOTO", {"roles": [{"training_role": ROLE, "requirement_code": "R"}], "high_hazard": 1}),
			("_T-RT-HAZCOM", {"roles": [{"training_role": ROLE, "requirement_code": "R"}]}),
			("_T-RT-OTHER", {}),
		):
			ensure(
				"Training Requirement",
				course,
				course_id=course,
				course_title=course,
				avenue="Safety / EHS",
				refresher_frequency="Annually",
				document_number="_T-DOC-1" if course == "_T-RT-HAZCOM" else course,
				**extra,
			)
		cls.employee = make_employee(
			"_t_retrain@example.com",
			company=ensure_company(),
			gender=ensure_gender(),
			designation=DESIGNATION,
		)

	def setUp(self):
		matrix = sync_matrix(self.employee)
		for r in matrix.items:
			r.completed_on = add_days(today(), -30)
		matrix.save()

	def test_incident_retraining_and_cancel(self):
		name = create_assignment(
			"Incident or Near Miss",
			[self.employee],
			["_T-RT-HAZCOM", "_T-RT-OTHER"],
			today(),
			add_days(today(), 14),
			"test",
		)
		hazcom = row(self.employee, "_T-RT-HAZCOM")
		self.assertEqual((hazcom.status, hazcom.qualification), (st.DUE, st.QUALIFIED))
		other = row(self.employee, "_T-RT-OTHER")  # not a role course: added for the retraining
		self.assertEqual((other.requirement_code, other.needed_for), (st.REQUIRED, "Retraining"))

		frappe.get_doc("Retraining Assignment", name).cancel()
		self.assertIsNone(row(self.employee, "_T-RT-HAZCOM").retrain_from)
		self.assertIsNone(row(self.employee, "_T-RT-OTHER"))  # dropped again on the next sync
		sync_matrix(self.employee)

	def test_return_from_absence_threshold(self):
		self.assertIsNone(record_return_from_absence(self.employee, add_days(today(), -30), today()))
		name = record_return_from_absence(self.employee, add_days(today(), -120), today())
		courses = {c.training_requirement for c in frappe.get_doc("Retraining Assignment", name).courses}
		self.assertEqual(courses, {"_T-RT-LOTO"})  # high-hazard only by default

	def test_document_revision_read_and_acknowledge(self):
		revision = frappe.get_doc(
			{
				"doctype": "Document Revision",
				"document_number": "_T-DOC-1",
				"revision": "2",
				"effective_date": today(),
				"change_summary": "Updated labels section",
				"courses": [
					{
						"training_requirement": "_T-RT-HAZCOM",
						"retraining": "Read & Acknowledge",
						"due_date": add_days(today(), 30),
					}
				],
			}
		)
		revision.insert()
		revision.submit()
		self.assertEqual(
			frappe.db.get_value("Training Requirement", "_T-RT-HAZCOM", "document_revision"), "2"
		)
		course = revision.courses[0]
		course.reload()
		record = frappe.get_doc("Training Record", course.training_record)
		self.assertEqual((record.source, record.status), ("Read & Acknowledge", "Awaiting Acknowledgment"))
		self.assertEqual(row(self.employee, "_T-RT-HAZCOM").status, st.IN_PROGRESS)
		revision.cancel()
		self.assertEqual(frappe.db.get_value("Training Record", record.name, "docstatus"), 2)

	def test_overdue_notice_then_escalation(self):
		matrix = frappe.get_doc("Employee Training Matrix", self.employee)
		target = next(r for r in matrix.items if r.training_requirement == "_T-RT-LOTO")
		target.completed_on = add_days(today(), -400)  # annual refresher lapsed
		matrix.save()
		overdue = row(self.employee, "_T-RT-LOTO")
		self.assertEqual(overdue.status, st.OVERDUE)
		process_overdue(today())
		self.assertEqual(str(row(self.employee, "_T-RT-LOTO").manager_notified_on), str(today()))
		self.assertIsNone(row(self.employee, "_T-RT-LOTO").escalated_on)
		process_overdue(add_days(overdue.overdue_since, 14))
		self.assertIsNotNone(row(self.employee, "_T-RT-LOTO").escalated_on)
