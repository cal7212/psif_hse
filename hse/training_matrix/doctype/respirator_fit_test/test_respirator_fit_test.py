# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_months, getdate, today

from hse.testing_fixtures import ensure_company, ensure_gender
from hse.training_matrix import skill_status as ss
from hse.training_matrix.evidence import FIT_TEST
from hse.training_matrix.matrix import sync_matrix
from hse.training_matrix.setup.respirator import TESTER_SKILL

DESIGNATION, ROLE, SKILL = "_T Resp Wearer", "_T Resp Role", "_T Respirator Wearer"
COURSE = "_T-FIT"


def ensure(doctype, name, **values):
	if not frappe.db.exists(doctype, name):
		doc = frappe.get_doc({"doctype": doctype, **values})
		doc.flags.skip_resync = True
		doc.insert()


class IntegrationTestRespiratorFitTest(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.setup.doctype.employee.test_employee import make_employee

		ensure("Designation", DESIGNATION, designation_name=DESIGNATION)
		ensure("Training Role", ROLE, role_name=ROLE, designations=[{"designation": DESIGNATION}])
		ensure(
			"Training Requirement",
			COURSE,
			course_id=COURSE,
			course_title="Fit test",
			avenue="Safety / EHS",
			verification_method=FIT_TEST,
			initial_due_basis="Date Assigned",
			refresher_frequency="Annually",
		)
		ensure("Skill", SKILL, skill_name=SKILL)
		ensure(
			"Skill Definition",
			SKILL,
			skill=SKILL,
			courses=[{"training_requirement": COURSE}],
			roles=[{"training_role": ROLE, "requirement_code": "R"}],
		)
		company, gender = ensure_company(), ensure_gender()
		cls.worker = make_employee(
			"_t_resp_worker@example.com", company=company, gender=gender, designation=DESIGNATION
		)
		cls.tester = make_employee("_t_resp_tester@example.com", company=company, gender=gender)
		ensure("Skill", TESTER_SKILL, skill_name=TESTER_SKILL)

	def setUp(self):
		frappe.set_user("Administrator")
		for name in frappe.get_all("Respirator Fit Test", filters={"employee": self.worker}, pluck="name"):
			frappe.db.delete("Respirator Fit Test", name)
		if frappe.db.exists("Employee Training Matrix", self.worker):
			frappe.delete_doc("Employee Training Matrix", self.worker, force=1, ignore_permissions=True)
		sync_matrix(self.worker)

	def fit_test(self, result="Pass", on=None, size="M", submit=True, **values):
		doc = frappe.get_doc(
			{
				"doctype": "Respirator Fit Test",
				"employee": self.worker,
				"test_date": on or today(),
				"result": result,
				"manufacturer": "TestCo",
				"model": "HM-100",
				"style": "Elastomeric Half Mask",
				"size": size,
				"test_type": "Qualitative (QLFT)",
				"protocol": "Bitrex",
				"tester_name": "Outside Tester",
				"provider": "Outside Co",
				"medical_clearance_date": add_days(on or today(), -7),
				"written_recommendation": 1,
				**values,
			}
		).insert()
		if submit:
			doc.submit()
		return doc

	def row(self):
		matrix = frappe.get_doc("Employee Training Matrix", self.worker)
		return next(r for r in matrix.items if r.training_requirement == COURSE)

	def skill_status(self):
		matrix = frappe.get_doc("Employee Training Matrix", self.worker)
		return next(s for s in matrix.skills if s.skill == SKILL).status

	def test_skill_brings_in_the_fit_test_course(self):
		self.assertIsNone(self.row().completed_on)
		self.assertEqual(self.skill_status(), ss.NOT_STARTED)

	def test_pass_qualifies_and_sets_next_due(self):
		doc = self.fit_test()
		self.assertEqual(getdate(doc.next_due_date), getdate(add_months(today(), 12)))
		row = self.row()
		self.assertEqual((getdate(row.completed_on), row.respirator_fit_test), (getdate(today()), doc.name))
		self.assertEqual(self.skill_status(), ss.READY)

	def test_failed_retest_on_same_respirator_withdraws_it(self):
		self.fit_test(on=add_days(today(), -30))
		self.fit_test("Fail")
		row = self.row()
		self.assertIsNone(row.completed_on)
		self.assertEqual(row.in_progress, 1)
		self.assertNotEqual(self.skill_status(), ss.READY)

	def test_other_respirator_still_counts(self):
		passed = self.fit_test(on=add_days(today(), -30), size="L")
		self.fit_test("Fail", size="M")
		self.assertEqual(self.row().respirator_fit_test, passed.name)

	def test_cancel_removes_the_evidence(self):
		doc = self.fit_test()
		doc.cancel()
		self.assertIsNone(self.row().completed_on)

	def test_old_pass_lapses(self):
		self.fit_test(on=add_days(today(), -400))
		self.assertNotEqual(self.skill_status(), ss.READY)

	def test_validation(self):
		with self.assertRaises(frappe.ValidationError):  # clearance after the test
			self.fit_test(medical_clearance_date=add_days(today(), 1), submit=False)
		with self.assertRaises(frappe.ValidationError):  # QNFT protocol on a QLFT test
			self.fit_test(protocol="CNP REDON", submit=False)
		with self.assertRaises(frappe.ValidationError):  # QNFT needs fit factor and printout
			self.fit_test(test_type="Quantitative (QNFT)", protocol="Generated Aerosol")
		with self.assertRaises(frappe.ValidationError):  # written recommendation not on file
			self.fit_test(written_recommendation=0)

	def set_tester_status(self, status):
		sync_matrix(self.tester)
		frappe.db.delete("Employee Training Matrix Skill", {"parent": self.tester, "skill": TESTER_SKILL})
		if status:
			frappe.get_doc(
				{
					"doctype": "Employee Training Matrix Skill",
					"parenttype": "Employee Training Matrix",
					"parentfield": "skills",
					"parent": self.tester,
					"skill": TESTER_SKILL,
					"needed_for": "Role",
					"status": status,
				}
			).db_insert()

	def test_in_house_tester_needs_the_skill(self):
		self.set_tester_status(None)
		with self.assertRaises(frappe.ValidationError):
			self.fit_test(tester=self.tester, provider=None)
		self.set_tester_status(ss.LAPSED)
		with self.assertRaises(frappe.ValidationError):
			self.fit_test(tester=self.tester, provider=None)
		self.set_tester_status(ss.AUTHORIZED)
		doc = self.fit_test(tester=self.tester, provider=None)
		self.assertEqual(doc.docstatus, 1)

	def test_outside_test_needs_a_provider(self):
		with self.assertRaises(frappe.ValidationError):
			self.fit_test(provider=None)
