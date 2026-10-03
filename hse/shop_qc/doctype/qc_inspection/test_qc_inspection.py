# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""bench --site <test-site> run-tests --module hse.shop_qc.doctype.qc_inspection.test_qc_inspection"""

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from hse.shop_qc.doctype.qc_inspection.qc_inspection import (
	FAIL,
	PASS,
	build_items,
	evaluate_hose,
	evaluate_numeric,
)
from hse.shop_qc.utils import certificate_format_for, get_stages, stage_applies

PROC = "_Test QC Procedure"
WO = "_TEST-WO-1"
HOSE_WO = "_TEST-HOSE-WO-1"
SHOP = "_T Shop"
HOSE_SHOP = "_T Hose Shop"
STAGES = [("_T Assembly", 10, 0), ("_T Test", 20, 0), ("_T Release", 30, 1)]
HOSE_STAGES = [("_T Hose Test", 10, 0, 1), ("_T Hose Release", 20, 1, 0)]


class UnitTestQCInspection(UnitTestCase):
	def test_hose_evaluation(self):
		row = frappe._dict(
			crimp_min=0.990,
			crimp_max=1.010,
			test_pressure_spec=6000,
			hold_time_spec=30,
			crimp_a=1.000,
			crimp_b=1.005,
			pressure_reached=6050,
			hold_time_actual=30,
			leak_check="No Leak",
		)
		self.assertEqual(evaluate_hose(row), PASS)
		self.assertEqual(evaluate_hose(frappe._dict(row, crimp_b=1.020)), FAIL)
		self.assertEqual(evaluate_hose(frappe._dict(row, pressure_reached=5900)), FAIL)
		self.assertEqual(evaluate_hose(frappe._dict(row, hold_time_actual=20)), FAIL)
		self.assertEqual(evaluate_hose(frappe._dict(row, leak_check="Leak")), FAIL)
		self.assertIsNone(evaluate_hose(frappe._dict(row, leak_check=None)))
		self.assertIsNone(evaluate_hose(frappe._dict(row, crimp_a=0)))
		# no crimp spec: crimp not required
		self.assertEqual(
			evaluate_hose(frappe._dict(row, crimp_min=0, crimp_max=0, crimp_a=0, crimp_b=0)), PASS
		)

	def test_stage_applies(self):
		st = frappe._dict(shop="HPU", job_type="New Build")
		self.assertTrue(stage_applies(st, "HPU", "New Build"))
		self.assertFalse(stage_applies(st, "Hose", "New Build"))
		self.assertFalse(stage_applies(st, "HPU", "Repair"))
		self.assertTrue(stage_applies(frappe._dict(shop=None, job_type="Repair"), "Hose", "Repair"))
		self.assertTrue(stage_applies(frappe._dict(shop=None, job_type="Both"), "Hose", "New Build"))

	def test_certificate_format(self):
		self.assertEqual(certificate_format_for("Repair", "Hose Assembly"), "QC Repair Report")
		self.assertEqual(
			certificate_format_for("New Build", "Hose Assembly"), "Hose Assembly Test Certificate"
		)
		self.assertEqual(certificate_format_for("New Build", "Valve Stand"), "Manifold QC Certificate")
		self.assertEqual(certificate_format_for("New Build", "Power Unit"), "Power Unit QC Certificate")

	def test_numeric_limits(self):
		self.assertEqual(evaluate_numeric(3000, 2910, 3090), PASS)
		self.assertEqual(evaluate_numeric(3100, 2910, 3090), FAIL)
		self.assertEqual(evaluate_numeric(2900, 2910, 3090), FAIL)
		self.assertEqual(evaluate_numeric(5), PASS)


class IntegrationTestQCInspection(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.set_value("QC Stage", {"name": ("not like", "_T %")}, "disabled", 1)
		if not frappe.db.exists("Quality Procedure", PROC):
			frappe.get_doc({"doctype": "Quality Procedure", "quality_procedure_name": PROC}).insert()
		for shop, prefix, mult in ((SHOP, "TQA", 0), (HOSE_SHOP, "TQH", 2)):
			if not frappe.db.exists("Build Shop", shop):
				frappe.get_doc(
					{
						"doctype": "Build Shop",
						"shop_name": shop,
						"inspection_prefix": prefix,
						"test_pressure_multiplier": mult,
						"default_hold_time_sec": 30,
					}
				).insert()
		for iid, itype, due in (
			("_T-G1", "Pressure Gauge", "2099-12-31"),
			("_T-G2", "Pressure Gauge", "2099-12-31"),
			("_T-CAL", "Caliper / Micrometer", "2099-12-31"),
			("_T-EXP", "Pressure Gauge", "2000-01-01"),
		):
			if not frappe.db.exists("Measuring Instrument", iid):
				frappe.get_doc(
					{
						"doctype": "Measuring Instrument",
						"instrument_id": iid,
						"instrument_type": itype,
						"calibration_due": due,
					}
				).insert()
		if not frappe.db.exists("QC Failure Cause", "Other"):
			frappe.get_doc({"doctype": "QC Failure Cause", "failure_cause": "Other"}).insert()
		for name, seq, final, hose in HOSE_STAGES:
			if not frappe.db.exists("QC Stage", name):
				frappe.get_doc(
					{
						"doctype": "QC Stage",
						"stage_name": name,
						"sequence": seq,
						"shop": HOSE_SHOP,
						"job_type": "New Build",
						"is_required": 1,
						"hold_point": 1,
						"is_final_release": final,
						"hose_test": hose,
					}
				).insert()
			tname = f"{name} Template"
			if not frappe.db.exists("QC Inspection Template", tname):
				frappe.get_doc(
					{
						"doctype": "QC Inspection Template",
						"template_name": tname,
						"stage": name,
						"product_type": "Hose Assembly",
						"quality_procedure": PROC,
						"items": [{"check_item": "Visual", "criteria": "OK"}],
					}
				).insert()
		for name, seq, final in STAGES:
			if not frappe.db.exists("QC Stage", name):
				frappe.get_doc(
					{
						"doctype": "QC Stage",
						"stage_name": name,
						"sequence": seq,
						"shop": SHOP,
						"job_type": "Both",
						"is_required": 1,
						"hold_point": 1,
						"is_final_release": final,
					}
				).insert()
			tname = f"{name} Template"
			if not frappe.db.exists("QC Inspection Template", tname):
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
						"doctype": "QC Inspection Template",
						"template_name": tname,
						"stage": name,
						"quality_procedure": PROC,
						"items": items,
					}
				).insert()
		cls.company = frappe.db.get_value("Company", {}, "name")
		cls.employee = frappe.db.get_value("Employee", {"status": "Active", "company": cls.company}, "name")
		if not cls.employee:
			cls.employee = (
				frappe.get_doc(
					{
						"doctype": "Employee",
						"first_name": "_Test HPU Inspector",
						"gender": frappe.db.get_value("Gender", {}, "name"),
						"date_of_birth": "1990-01-01",
						"date_of_joining": "2020-01-01",
						"company": cls.company,
						"status": "Active",
					}
				)
				.insert()
				.name
			)

	def clear_unit(self, unit):
		if not frappe.db.exists("QC Unit", unit):
			return
		# Remove records left by earlier tests directly; cancelling would trip the
		# "resolved by this re-inspection" guard.
		names = frappe.get_all("QC Inspection", {"qc_unit": unit}, pluck="name")
		if names:
			frappe.db.delete("QC Inspection Reading", {"parent": ("in", names)})
			frappe.db.delete("QC Hose Test", {"parent": ("in", names)})
		frappe.db.delete("QC Inspection", {"qc_unit": unit})
		frappe.db.delete("Non Conformance", {"qc_unit": unit})
		frappe.delete_doc("QC Unit", unit, force=1)

	def setUp(self):
		for unit in (WO, HOSE_WO, "_TEST-HOSE-WO-2", "RGA-_T100"):
			self.clear_unit(unit)
		frappe.get_doc(
			{
				"doctype": "QC Unit",
				"shop": SHOP,
				"product_type": "Power Unit",
				"job_type": "New Build",
				"trulinx_work_order": WO,
				"model": "HPU-30-460-3",
				"company": self.company,
				"relief_setting_psi": 3000,
			}
		).insert()

	def make_hose_unit(self):
		hose = {"working_pressure_psi": 3000, "crimp_diameter_spec": 1.0, "crimp_tolerance": 0.01}
		return frappe.get_doc(
			{
				"doctype": "QC Unit",
				"shop": HOSE_SHOP,
				"product_type": "Hose Assembly",
				"job_type": "New Build",
				"trulinx_work_order": HOSE_WO,
				"model": "HOSE-8",
				"company": self.company,
				"hoses": [dict(hose, hose_tag="_TH-1"), dict(hose, hose_tag="_TH-2")],
			}
		).insert()

	def default_instruments(self, unit):
		return ["_T-G1", "_T-CAL"] if unit == HOSE_WO else ["_T-G1"]

	def make(
		self,
		stage,
		results=None,
		reading=None,
		submit=True,
		unit=WO,
		hose_values=None,
		instruments=None,
		**kw,
	):
		doc = frappe.get_doc(
			{
				"doctype": "QC Inspection",
				"qc_unit": unit,
				"stage": stage,
				"template": f"{stage} Template",
				"inspected_by": self.employee,
				"instruments": [{"instrument": i} for i in (instruments or self.default_instruments(unit))],
				**kw,
			}
		)
		doc.insert()
		for row in doc.items:
			if row.numeric:
				row.reading_value = reading
				# Out-of-limit readings auto-fail on save, and a failed line needs a finding.
				row.finding = "Reading recorded by test"
			else:
				row.result = (results or {}).get(row.check_item, PASS)
				if row.result == FAIL:
					row.finding = "Test failure"
		for h in doc.hose_tests:
			h.update((hose_values or {}).get(h.hose_tag, {}))
			h.finding = h.finding or "Recorded by test"
		doc.save()
		if submit:
			doc.submit()
		return doc

	def status(self):
		return frappe.db.get_value("QC Unit", WO, "status")

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
		self.assertEqual(nc.qc_reinspection, re.name)
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
		self.assertTrue(frappe.db.get_value("QC Unit", WO, "released_on"))

	def test_shop_prefix_naming(self):
		doc = self.make("_T Assembly", submit=False)
		self.assertTrue(doc.name.startswith("TQA-"))
		self.assertEqual(doc.shop, SHOP)

	def test_stage_from_other_shop_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.make("_T Hose Test", submit=False)

	def test_hose_unit_defaults_and_tests(self):
		unit = self.make_hose_unit()
		self.assertEqual(unit.hose_count, 2)
		self.assertEqual(unit.hoses[0].test_pressure_psi, 6000)  # 3000 x multiplier 2
		self.assertEqual(unit.hoses[0].hold_time_sec, 30)
		self.assertEqual([s.name for s in get_stages(HOSE_WO)], ["_T Hose Test", "_T Hose Release"])
		good = {
			"crimp_a": 1.0,
			"crimp_b": 1.0,
			"pressure_reached": 6100,
			"hold_time_actual": 30,
			"leak_check": "No Leak",
		}
		bad = dict(good, leak_check="Leak")
		first = self.make("_T Hose Test", unit=HOSE_WO, hose_values={"_TH-1": good, "_TH-2": bad})
		self.assertTrue(first.name.startswith("TQH-"))
		self.assertEqual(first.status, "Rejected")
		nc = frappe.db.get_value(
			"Non Conformance", first.non_conformance, ["severity", "details"], as_dict=True
		)
		self.assertEqual(nc.severity, "Critical")
		self.assertIn("_TH-2", nc.details)
		retest = self.make(
			"_T Hose Test",
			unit=HOSE_WO,
			hose_values={"_TH-2": good},
			is_reinspection=1,
			reinspection_of=first.name,
		)
		self.assertEqual([h.hose_tag for h in retest.hose_tests], ["_TH-2"])
		self.assertEqual(retest.status, "Accepted")

	def test_duplicate_hose_tag_rejected(self):
		self.make_hose_unit()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "QC Unit",
					"shop": HOSE_SHOP,
					"product_type": "Hose Assembly",
					"trulinx_work_order": "_TEST-HOSE-WO-2",
					"model": "HOSE-8",
					"company": self.company,
					"hoses": [{"hose_tag": "_th-1"}],
				}
			).insert()

	def test_repair_named_by_rga_and_release_gate(self):
		unit = frappe.get_doc(
			{
				"doctype": "QC Unit",
				"shop": SHOP,
				"product_type": "Power Unit",
				"job_type": "Repair",
				"rga_number": "_t100",
				"model": "HPU-30-460-3",
				"company": self.company,
				"received_date": frappe.utils.nowdate(),
				"reported_problem": "Noisy pump",
				"relief_setting_psi": 3000,
			}
		).insert()
		self.assertEqual(unit.name, "RGA-_T100")
		self.make("_T Assembly", unit=unit.name)
		self.make("_T Test", unit=unit.name, reading=3000)
		with self.assertRaises(frappe.ValidationError):
			self.make("_T Release", unit=unit.name)  # failure cause, work performed, disposition missing
		frappe.db.set_value(
			"QC Unit",
			unit.name,
			{"failure_cause": "Other", "work_performed": "Replaced pump", "disposition": "Repair"},
		)
		self.make("_T Release", unit=unit.name)
		self.assertEqual(frappe.db.get_value("QC Unit", unit.name, "status"), "Released")

	def test_expired_instrument_blocks_submit(self):
		self.make("_T Assembly")
		with self.assertRaises(frappe.ValidationError):
			self.make("_T Test", reading=3000, instruments=["_T-EXP"])

	def test_single_instrument_fills_readings(self):
		self.make("_T Assembly")
		doc = self.make("_T Test", reading=3000, instruments=["_T-G1"])
		self.assertTrue(all(r.instrument == "_T-G1" for r in doc.items if r.numeric))
		self.assertEqual(str(doc.instruments[0].calibration_due), "2099-12-31")

	def test_two_instruments_need_reading_instrument(self):
		self.make("_T Assembly")
		with self.assertRaises(frappe.ValidationError):
			self.make("_T Test", reading=3000, instruments=["_T-G1", "_T-G2"])
		doc = self.make("_T Test", reading=3000, instruments=["_T-G1", "_T-G2"], submit=False)
		for r in doc.items:
			if r.numeric:
				r.instrument = "_T-G2"
		doc.save()
		doc.submit()
		self.assertEqual(doc.status, "Accepted")

	def test_reading_instrument_added_to_table(self):
		self.make("_T Assembly")
		doc = self.make("_T Test", reading=3000, instruments=["_T-G1"], submit=False)
		for r in doc.items:
			if r.numeric:
				r.instrument = "_T-G2"
		doc.save()
		self.assertEqual(sorted(i.instrument for i in doc.instruments), ["_T-G1", "_T-G2"])

	def test_hose_instruments_picked_by_type(self):
		self.make_hose_unit()
		good = {
			"crimp_a": 1.0,
			"crimp_b": 1.0,
			"pressure_reached": 6100,
			"hold_time_actual": 30,
			"leak_check": "No Leak",
		}
		doc = self.make("_T Hose Test", unit=HOSE_WO, hose_values={"_TH-1": good, "_TH-2": good})
		self.assertTrue(
			all(h.instrument == "_T-G1" and h.crimp_instrument == "_T-CAL" for h in doc.hose_tests)
		)
