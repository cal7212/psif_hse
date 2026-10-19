# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from hse.testing_fixtures import ensure_company, ensure_gender
from hse.training_matrix import skill_status as ss
from hse.training_matrix import status as st
from hse.training_matrix.matrix import sync_matrix
from hse.training_matrix.skills import set_target_skill

DESIGNATION, ROLE = "_T Skill Mech", "_T Skill Role"
MECH, TECH = "_T Mechanical", "_T Technician"


def ensure(doctype, name, **values):
	if not frappe.db.exists(doctype, name):
		doc = frappe.get_doc({"doctype": doctype, **values})
		doc.flags.skip_resync = True
		doc.insert()


class IntegrationTestSkillAuthorization(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.setup.doctype.employee.test_employee import make_employee

		ensure("Designation", DESIGNATION, designation_name=DESIGNATION)
		ensure("Training Role", ROLE, role_name=ROLE, designations=[{"designation": DESIGNATION}])
		for course in ("_T-MECH", "_T-TECH"):
			ensure(
				"Training Requirement",
				course,
				course_id=course,
				course_title=course,
				avenue="Technical",
				refresher_frequency="Annually",
			)
		for skill in (MECH, TECH):
			ensure("Skill", skill, skill_name=skill)
		ensure(
			"Skill Definition",
			MECH,
			skill=MECH,
			courses=[{"training_requirement": "_T-MECH"}],
			roles=[{"training_role": ROLE, "requirement_code": "R"}],
		)
		ensure(
			"Skill Definition",
			TECH,
			skill=TECH,
			prerequisites=[{"skill": MECH}],
			courses=[{"training_requirement": "_T-TECH"}],
		)
		cls.manager_user = "_t_skill_manager@example.com"
		company, gender = ensure_company(), ensure_gender()
		cls.manager = make_employee(cls.manager_user, company=company, gender=gender, designation=DESIGNATION)
		cls.worker = make_employee(
			"_t_skill_worker@example.com", company=company, gender=gender, designation=DESIGNATION
		)
		frappe.db.set_value("Employee", cls.worker, "reports_to", cls.manager)
		frappe.get_doc("User", cls.manager_user).add_roles("Employee")

	def tearDown(self):
		frappe.set_user("Administrator")

	def skill_row(self, skill):
		return next(
			s for s in frappe.get_doc("Employee Training Matrix", self.worker).skills if s.skill == skill
		)

	def complete(self, course, on):
		matrix = frappe.get_doc("Employee Training Matrix", self.worker)
		row = next(r for r in matrix.items if r.training_requirement == course)
		row.completed_on = on
		matrix.save()

	def authorize(self, user):
		frappe.set_user(user)
		doc = frappe.get_doc({"doctype": "Skill Authorization", "employee": self.worker, "skill": MECH})
		doc.insert()
		doc.submit()
		frappe.set_user("Administrator")
		return doc

	def hr_proficiency(self, skill):
		rows = frappe.get_all(
			"Employee Skill",
			filters={"parent": self.worker, "parenttype": "Employee Skill Map", "skill": skill},
			pluck="proficiency",
		)
		return rows[0] if rows else None

	def test_role_skill_flow(self):
		matrix = sync_matrix(self.worker)
		self.assertIn("_T-MECH", {r.training_requirement for r in matrix.items})
		self.assertEqual(self.skill_row(MECH).status, ss.NOT_STARTED)
		self.assertEqual(self.hr_proficiency(MECH), 0)  # needed by the role, shown at zero

		self.assertRaises(frappe.ValidationError, self.authorize, self.manager_user)  # not ready yet
		frappe.set_user("Administrator")

		self.complete("_T-MECH", today())
		self.assertEqual(self.skill_row(MECH).status, ss.READY)

		self.authorize(self.manager_user)
		self.assertEqual(self.skill_row(MECH).status, ss.AUTHORIZED)
		self.assertEqual(self.hr_proficiency(MECH), 1)

		self.complete("_T-MECH", add_days(today(), -400))  # annual refresher lapsed
		self.assertEqual(self.skill_row(MECH).status, ss.LAPSED)
		self.assertEqual(self.hr_proficiency(MECH), 0)

	def test_only_the_manager_can_authorize(self):
		sync_matrix(self.worker)
		self.complete("_T-MECH", today())
		self.assertRaises(frappe.PermissionError, self.authorize, "_t_skill_worker@example.com")

	def test_target_skill_adds_development_training(self):
		sync_matrix(self.worker)
		set_target_skill(self.worker, TECH, add_days(today(), 90))
		matrix = frappe.get_doc("Employee Training Matrix", self.worker)
		row = next(r for r in matrix.items if r.training_requirement == "_T-TECH")
		self.assertEqual((row.requirement_code, row.is_required), (st.DEVELOPMENT, 0))
		self.assertEqual(self.skill_row(TECH).needed_for, "Target")
