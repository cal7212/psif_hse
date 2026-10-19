# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from hse.testing_fixtures import ensure_company, ensure_gender
from hse.training_matrix import status as st
from hse.training_matrix.matrix import sync_matrix

TECH, OFFICE = "_T Training Tech", "_T Training Office"


def make_designation(name):
	if not frappe.db.exists("Designation", name):
		frappe.get_doc({"doctype": "Designation", "designation_name": name}).insert()


def make_role(name, designation):
	if frappe.db.exists("Training Role", name):
		return
	doc = frappe.get_doc(
		{"doctype": "Training Role", "role_name": name, "designations": [{"designation": designation}]}
	)
	doc.flags.skip_resync = True
	doc.insert()


def make_requirement(course_id, roles=(), all_employees=0, refresher="Annually", basis=st.ASSIGNED, days=0):
	if frappe.db.exists("Training Requirement", course_id):
		return
	doc = frappe.get_doc(
		{
			"doctype": "Training Requirement",
			"course_id": course_id,
			"course_title": f"Test course {course_id}",
			"avenue": "Safety / EHS",
			"all_employees": all_employees,
			"initial_due_basis": basis,
			"initial_due_days": days,
			"refresher_frequency": refresher,
			"roles": [{"training_role": r, "requirement_code": c} for r, c in roles],
		}
	)
	doc.flags.skip_resync = True
	doc.insert()


class IntegrationTestEmployeeTrainingMatrix(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.setup.doctype.employee.test_employee import make_employee

		for d in (TECH, OFFICE):
			make_designation(d)
		make_role("_T Technician", TECH)
		make_role("_T Office", OFFICE)
		make_requirement("_T-ALL", all_employees=1, basis=st.HIRE, days=30)
		make_requirement("_T-LOTO", roles=[("_T Technician", "R")])
		make_requirement("_T-70E", roles=[("_T Technician", "C"), ("_T Office", "C")])
		make_requirement("_T-CPR", roles=[("_T Technician", "R")], refresher=st.PER_CERTIFICATION)
		make_requirement("_T-RECORDS", roles=[("_T Office", "R")])
		cls.employee = make_employee(
			"_t_training_matrix@example.com",
			company=ensure_company(),
			gender=ensure_gender(),
			designation=TECH,
			date_of_joining=add_days(today(), -10),
		)

	def matrix(self):
		return sync_matrix(self.employee)

	def codes(self, matrix):
		return {r.training_requirement: r.requirement_code for r in matrix.items}

	def test_rows_follow_role_and_all_employees(self):
		frappe.db.set_value("Employee", self.employee, "designation", TECH)
		matrix = self.matrix()
		self.assertEqual([r.training_role for r in matrix.roles], ["_T Technician"])
		codes = self.codes(matrix)
		self.assertEqual(codes.get("_T-ALL"), st.REQUIRED)
		self.assertEqual(codes.get("_T-LOTO"), st.REQUIRED)
		self.assertEqual(codes.get("_T-70E"), st.CONDITIONAL)
		self.assertNotIn("_T-RECORDS", codes)
		row = next(r for r in matrix.items if r.training_requirement == "_T-70E")
		self.assertEqual(row.status, st.CONFIRM)
		self.assertGreaterEqual(matrix.confirm_count, 1)

	def test_job_change_keeps_history_and_drops_untrained_rows(self):
		frappe.db.set_value("Employee", self.employee, "designation", TECH)
		matrix = self.matrix()
		next(r for r in matrix.items if r.training_requirement == "_T-LOTO").completed_on = today()
		matrix.save()

		frappe.db.set_value("Employee", self.employee, "designation", OFFICE)
		matrix = self.matrix()
		codes = self.codes(matrix)
		self.assertEqual(codes.get("_T-LOTO"), st.NOT_REQUIRED)  # trained, kept as history
		self.assertNotIn("_T-CPR", codes)  # never trained, removed
		self.assertEqual(codes.get("_T-RECORDS"), st.REQUIRED)
		loto = next(r for r in matrix.items if r.training_requirement == "_T-LOTO")
		self.assertEqual((loto.status, loto.qualification), (st.NOT_APPLICABLE, st.QUALIFIED))

	def test_completion_makes_row_qualified(self):
		frappe.db.set_value("Employee", self.employee, "designation", TECH)
		matrix = self.matrix()
		row = next(r for r in matrix.items if r.training_requirement == "_T-ALL")
		row.completed_on = today()
		matrix.save()
		row = next(r for r in matrix.items if r.training_requirement == "_T-ALL")
		self.assertEqual((row.status, row.qualification), (st.COMPLETED, st.QUALIFIED))
		self.assertEqual(str(row.first_completed_on), str(today()))
		self.assertGreater(matrix.percent_complete, 0)

	def test_certificate_needs_expiry(self):
		frappe.db.set_value("Employee", self.employee, "designation", TECH)
		matrix = self.matrix()
		row = next(r for r in matrix.items if r.training_requirement == "_T-CPR")
		row.completed_on = today()
		row.expires_on = None
		self.assertRaises(frappe.ValidationError, matrix.save)

	def test_future_completion_rejected(self):
		matrix = self.matrix()
		matrix.items[0].completed_on = add_days(today(), 5)
		self.assertRaises(frappe.ValidationError, matrix.save)


class IntegrationTestEmployeeGroupMapping(IntegrationTestCase):
	def test_group_membership_assigns_role(self):
		from erpnext.setup.doctype.employee.test_employee import make_employee

		employee = make_employee(
			"_t_group_member@example.com",
			company=ensure_company(),
			gender=ensure_gender(),
			designation=OFFICE,
		)
		if not frappe.db.exists("Employee Group", "_T Respirator Users"):
			frappe.get_doc(
				{"doctype": "Employee Group", "employee_group_name": "_T Respirator Users"}
			).insert()
		if not frappe.db.exists("Training Role", "_T Respirator"):
			role = frappe.get_doc(
				{
					"doctype": "Training Role",
					"role_name": "_T Respirator",
					"employee_groups": [{"employee_group": "_T Respirator Users"}],
				}
			)
			role.flags.skip_resync = True
			role.insert()
		make_requirement("_T-RESP", roles=[("_T Respirator", "R")])

		group = frappe.get_doc("Employee Group", "_T Respirator Users")
		group.append("employee_list", {"employee": employee})
		group.save()
		matrix = frappe.get_doc("Employee Training Matrix", employee)
		self.assertIn("_T Respirator", [r.training_role for r in matrix.roles])
		self.assertIn("_T-RESP", {r.training_requirement for r in matrix.items})

		group.set("employee_list", [r for r in group.employee_list if r.employee != employee])
		group.save()
		matrix = frappe.get_doc("Employee Training Matrix", employee)
		self.assertNotIn("_T Respirator", [r.training_role for r in matrix.roles])
		self.assertNotIn("_T-RESP", {r.training_requirement for r in matrix.items})
