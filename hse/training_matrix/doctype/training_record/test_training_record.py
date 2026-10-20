# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today

from hse.testing_fixtures import ensure_company, ensure_gender
from hse.training_matrix import status as st
from hse.training_matrix.matrix import sync_matrix

DESIGNATION = "_T Record Tech"
ROLE = "_T Record Role"


def make_requirement(course_id, verification, high_hazard=0):
	if frappe.db.exists("Training Requirement", course_id):
		return
	doc = frappe.get_doc(
		{
			"doctype": "Training Requirement",
			"course_id": course_id,
			"course_title": f"Test {course_id}",
			"avenue": "Safety / EHS",
			"verification_method": verification,
			"requires_qualified_trainer": high_hazard,
			"high_hazard": high_hazard,
			"refresher_frequency": "Annually",
			"roles": [{"training_role": ROLE, "requirement_code": "R"}],
		}
	)
	doc.flags.skip_resync = True
	doc.insert()


def row_for(employee, course):
	return next(
		r
		for r in frappe.get_doc("Employee Training Matrix", employee).items
		if r.training_requirement == course
	)


class IntegrationTestTrainingRecord(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.setup.doctype.employee.test_employee import make_employee

		if not frappe.db.exists("Designation", DESIGNATION):
			frappe.get_doc({"doctype": "Designation", "designation_name": DESIGNATION}).insert()
		if not frappe.db.exists("Training Role", ROLE):
			role = frappe.get_doc(
				{
					"doctype": "Training Role",
					"role_name": ROLE,
					"designations": [{"designation": DESIGNATION}],
				}
			)
			role.flags.skip_resync = True
			role.insert()
		make_requirement("_T-QUIZ", "Quiz (80%)")
		make_requirement("_T-PRAC", "Practical Demonstration")
		make_requirement("_T-HAZ", "Practical Evaluation", high_hazard=1)
		company, gender = ensure_company(), ensure_gender()
		cls.trainee = make_employee(
			"_t_trainee@example.com", company=company, gender=gender, designation=DESIGNATION
		)
		cls.trainer = make_employee(
			"_t_trainer@example.com", company=company, gender=gender, designation=DESIGNATION
		)
		for emp in (cls.trainee, cls.trainer):
			sync_matrix(emp)

	def record(self, course, source="Classroom", trainer=None, **attendee):
		doc = frappe.get_doc(
			{
				"doctype": "Training Record",
				"training_requirement": course,
				"training_date": today(),
				"source": source,
				"trainer": trainer or self.trainer,
				"attendees": [{"employee": self.trainee, **attendee}],
			}
		)
		doc.insert()
		return doc

	def acknowledge(self, doc):
		row = doc.attendees[0]
		row.db_set({"acknowledged": 1, "acknowledged_on": frappe.utils.now_datetime()})
		from hse.training_matrix.evidence import recalculate

		recalculate(self.trainee, doc.training_requirement)

	def test_quiz_score_sets_result(self):
		doc = self.record("_T-QUIZ", score=70)
		self.assertEqual(doc.attendees[0].result, "Fail")

	def test_classroom_counts_after_acknowledgment(self):
		doc = self.record("_T-QUIZ", score=90)
		doc.submit()
		self.assertEqual(doc.status, "Awaiting Acknowledgment")
		self.assertEqual(row_for(self.trainee, "_T-QUIZ").status, st.IN_PROGRESS)
		self.acknowledge(doc)
		row = row_for(self.trainee, "_T-QUIZ")
		self.assertEqual((row.qualification, row.training_record), (st.QUALIFIED, doc.name))
		doc.cancel()
		self.assertNotEqual(row_for(self.trainee, "_T-QUIZ").qualification, st.QUALIFIED)

	def test_practical_course_waits_for_evaluation(self):
		doc = self.record("_T-PRAC")
		doc.submit()
		self.acknowledge(doc)
		self.assertEqual(row_for(self.trainee, "_T-PRAC").status, st.IN_PROGRESS)
		evaluation = frappe.get_doc(
			{
				"doctype": "Competency Evaluation",
				"employee": self.trainee,
				"training_requirement": "_T-PRAC",
				"training_record": doc.name,
				"evaluator": self.trainer,
				"checklist": [{"item": "Demonstrates the task", "result": "Pass"}],
			}
		)
		evaluation.insert()
		evaluation.submit()
		self.assertEqual(evaluation.result, "Pass")
		row = row_for(self.trainee, "_T-PRAC")
		self.assertEqual((row.qualification, row.competency_evaluation), (st.QUALIFIED, evaluation.name))

	def test_high_hazard_needs_qualified_trainer(self):
		self.assertRaises(frappe.ValidationError, self.record, "_T-HAZ")

	def test_trainer_must_be_qualified_to_be_designated(self):
		register = frappe.get_doc(
			{
				"doctype": "Qualified Trainer",
				"employee": self.trainer,
				"courses": [{"training_requirement": "_T-HAZ", "designated_by": "Administrator"}],
			}
		)
		self.assertRaises(frappe.ValidationError, register.insert)

	def test_prior_experience_needs_evidence(self):
		evaluation = frappe.get_doc(
			{
				"doctype": "Competency Evaluation",
				"employee": self.trainee,
				"training_requirement": "_T-PRAC",
				"basis": "Prior Experience",
				"evaluator": self.trainer,
				"result": "Pass",
			}
		)
		self.assertRaises(frappe.ValidationError, evaluation.insert)
