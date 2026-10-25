# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hse.training_matrix.evidence import FIT_TEST
from hse.training_matrix.setup import respirator


class IntegrationTestRespiratorSetup(IntegrationTestCase):
	def test_setup_creates_the_skill_once(self):
		respirator.setup()
		self.assertEqual(
			frappe.db.get_value("Training Requirement", respirator.FIT_TEST_COURSE, "verification_method"),
			FIT_TEST,
		)
		definition = frappe.get_doc("Skill Definition", respirator.SKILL)
		self.assertIn(respirator.FIT_TEST_COURSE, [c.training_requirement for c in definition.courses])
		self.assertEqual([r.training_role for r in definition.roles], [respirator.ROLE])
		groups = frappe.get_all(
			"Training Role Employee Group", filters={"parent": respirator.ROLE}, pluck="employee_group"
		)
		self.assertEqual(groups, [respirator.GROUP])
		tester = frappe.get_doc("Skill Definition", respirator.TESTER_SKILL)
		self.assertEqual([c.training_requirement for c in tester.courses], [respirator.TESTER_COURSE])
		self.assertEqual([r.training_role for r in tester.roles], [respirator.TESTER_ROLE])
		self.assertEqual(tester.authorizer_role, "Safety Manager")
		self.assertIsNone(frappe.get_doc("Skill Definition", respirator.SKILL).authorizer_role)
		self.assertEqual(
			frappe.db.get_value("Training Requirement", respirator.TESTER_COURSE, "verification_method"),
			"Practical Evaluation",
		)
		self.assertEqual(respirator.setup(), [])
		frappe.db.set_value("Skill Definition", respirator.TESTER_SKILL, "authorizer_role", None)
		self.assertEqual(respirator.set_authorizer_roles(), [respirator.TESTER_SKILL])
		self.assertEqual(respirator.set_authorizer_roles(), [])
