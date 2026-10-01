# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""bench --site <test-site> run-tests --module hse.hpu_build.doctype.hpu_build_inspection.test_hpu_build_inspection"""

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from hse.hpu_build.doctype.hpu_build_inspection.hpu_build_inspection import (
	FAIL,
	PASS,
	build_items,
	evaluate_numeric,
)

PROC = "_Test HPU Procedure"
WO = "_TEST-WO-1"
STAGES = [("_T Assembly", 10, 0), ("_T Test", 20, 0), ("_T Release", 30, 1)]


class UnitTestHPUBuildInspection(UnitTestCase):
	def test_numeric_limits(self):
		self.assertEqual(evaluate_numeric(3000, 2910, 3090), PASS)
		self.assertEqual(evaluate_numeric(3100, 2910, 3090), FAIL)
		self.assertEqual(evaluate_numeric(2900, 2910, 3090), FAIL)
		self.assertEqual(evaluate_numeric(5), PASS)


class IntegrationTestHPUBuildInspection(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.set_value("HPU Build Stage", {"name": ("not like", "_T %")}, "disabled", 1)
		if not frappe.db.exists("Quality Procedure", PROC):
			frappe.get_doc({"doctype": "Quality Procedure", "quality_procedure_name": PROC}).insert()
		for name, seq, final in STAGES:
			if not frappe.db.exists("HPU Build Stage", name):
				frappe.get_doc(
					{
						"doctype": "HPU Build Stage",
						"stage_name": name,
						"sequence": seq,
						"is_required": 1,
						"hold_point": 1,
						"is_final_release": final,
					}
				).insert()
			tname = f"{name} Template"
			if not frappe.db.exists("HPU Build Inspection Template", tname):
				items = [{"check_item": "Visual", "criteria": "OK"}]
				if name == "_T Test":
					items.append(
						{
							"check_item": "Relief setting",
							"numeric": 1,
							"unit_spec_field": "relief_setting_psi",
							"tolerance_minus_pct": 3,
							"tolerance_plus_pct": 3,
							"is_critical": 1,
						}
					)
				frappe.get_doc(
					{
						"doctype": "HPU Build Inspection Template",
						"template_name": tname,
						"stage": name,
						"quality_procedure": PROC,
						"items": items,
					}
				).insert()
		cls.company = frappe.db.get_value("Company", {}, "name")
		cls.employee = frappe.db.get_value("Employee", {"status": "Active"}, "name")

	def setUp(self):
		if frappe.db.exists("HPU Unit", WO):
			for n in frappe.get_all("HPU Build Inspection", {"hpu_unit": WO, "docstatus": 1}, pluck="name"):
				frappe.get_doc("HPU Build Inspection", n).cancel()
			frappe.db.delete("HPU Build Inspection", {"hpu_unit": WO})
			frappe.db.delete("Non Conformance", {"hpu_unit": WO})
			frappe.delete_doc("HPU Unit", WO, force=1)
		frappe.get_doc(
			{
				"doctype": "HPU Unit",
				"trulinx_work_order": WO,
				"model": "HPU-30-460-3",
				"company": self.company,
				"relief_setting_psi": 3000,
			}
		).insert()

	def make(self, stage, results=None, reading=None, submit=True, **kw):
		doc = frappe.get_doc(
			{
				"doctype": "HPU Build Inspection",
				"hpu_unit": WO,
				"stage": stage,
				"template": f"{stage} Template",
				"inspected_by": self.employee,
				"gauge_id": "G-1",
				"gauge_cal_due": "2099-12-31",
				**kw,
			}
		)
		doc.insert()
		for row in doc.items:
			if row.numeric:
				row.reading_value = reading
			else:
				row.result = (results or {}).get(row.check_item, PASS)
				if row.result == FAIL:
					row.finding = "Test failure"
		doc.save()
		if submit:
			doc.submit()
		return doc

	def status(self):
		return frappe.db.get_value("HPU Unit", WO, "status")

	def test_spec_limits_from_unit(self):
		rows = [r for r in build_items("_T Test Template", WO) if r["numeric"]]
		self.assertAlmostEqual(rows[0]["min_value"], 2910)
		self.assertAlmostEqual(rows[0]["max_value"], 3090)

	def test_hold_point_blocks_out_of_order(self):
		with self.assertRaises(frappe.ValidationError):
			self.make("_T Test", reading=3000)

	def test_reject_creates_nc_and_qc_hold(self):
		self.make("_T Assembly")
		self.assertEqual(self.status(), "In Build")
		bad = self.make("_T Test", reading=3200)
		self.assertEqual(bad.status, "Rejected")
		self.assertTrue(bad.non_conformance)
		self.assertEqual(frappe.db.get_value("Non Conformance", bad.non_conformance, "severity"), "Critical")
		self.assertEqual(self.status(), "QC Hold")
		with self.assertRaises(frappe.ValidationError):
			self.make("_T Release")  # hold point: _T Test not accepted

	def test_full_release_path(self):
		self.make("_T Assembly")
		bad = self.make("_T Test", reading=3200)
		re = self.make("_T Test", reading=3010, is_reinspection=1, reinspection_of=bad.name)
		self.assertEqual(re.status, "Accepted")
		nc = frappe.get_doc("Non Conformance", bad.non_conformance)
		self.assertEqual(nc.hpu_reinspection, re.name)
		nc.update(
			{
				"status": "Resolved",
				"corrective_action": "Reset relief valve",
				"verified_by": self.employee,
				"verification_date": frappe.utils.nowdate(),
			}
		)
		nc.save()
		self.assertEqual(self.status(), "Ready for Release")
		self.make("_T Release")
		self.assertEqual(self.status(), "Released")
		self.assertTrue(frappe.db.get_value("HPU Unit", WO, "released_on"))
