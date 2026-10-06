# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""bench --site <test-site> run-tests --module hse.shop_qc.doctype.qc_inspection.test_qc_inspection"""

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from hse.shop_qc.doctype.qc_inspection.qc_inspection import (
	FAIL,
	PASS,
	build_hose_tests,
	build_items,
	crimp_status,
	evaluate_accumulator,
	evaluate_hose,
	evaluate_numeric,
	evaluate_pmg,
	evaluate_proof,
	get_stage_test_rows,
)
from hse.shop_qc.doctype.qc_unit.qc_unit import crimp_diameter_warning, hose_spec, normalise_dash
from hse.shop_qc.utils import certificate_format_for, get_stages, stage_applies

PROC = "_Test QC Procedure"
WO = "_TEST-WO-1"
HOSE_WO = "_TEST-HOSE-WO-1"
SHOP = "_T Shop"
HOSE_SHOP = "_T Hose Shop"
STAGES = [("_T Assembly", 10, 0), ("_T Test", 20, 0), ("_T Release", 30, 1)]
HOSE_STAGES = [("_T Hose Test", 10, 0, 1), ("_T Hose Release", 20, 1, 0)]


class UnitTestQCInspection(UnitTestCase):
	def test_proof_and_accumulator_evaluation(self):
		row = frappe._dict(p1_spec=4500, p1_psi=4500, leak_check="No Leak")
		self.assertEqual(evaluate_proof(row), PASS)
		self.assertEqual(evaluate_proof(frappe._dict(row, p1_psi=4400)), FAIL)
		self.assertEqual(evaluate_proof(frappe._dict(row, leak_check="Leak")), FAIL)
		self.assertIsNone(evaluate_proof(frappe._dict(row, leak_check=None)))
		self.assertIsNone(evaluate_proof(frappe._dict(row, p2_spec=6000)))  # P2 not entered yet
		self.assertEqual(evaluate_proof(frappe._dict(row, p2_spec=6000, p2_psi=6000)), PASS)
		acc = frappe._dict(precharge_spec=1000, tolerance_psi=50, precharge_actual=1030)
		self.assertEqual(evaluate_accumulator(acc), PASS)
		self.assertEqual(evaluate_accumulator(frappe._dict(acc, precharge_actual=900)), FAIL)
		self.assertIsNone(evaluate_accumulator(frappe._dict(acc, tolerance_psi=0)))

	def test_pmg_evaluation(self):
		row = frappe._dict(
			relief_spec=3000,
			compensator_spec=2800,
			tolerance_psi=50,
			nameplate_verified="Yes",
			rotation_verified="Yes",
			relief_as_set=3020,
			compensator_as_set=2790,
		)
		self.assertEqual(evaluate_pmg(row), PASS)
		self.assertEqual(evaluate_pmg(frappe._dict(row, relief_as_set=3100)), FAIL)
		self.assertEqual(evaluate_pmg(frappe._dict(row, compensator_as_set=0)), "")  # incomplete
		self.assertEqual(evaluate_pmg(frappe._dict(row, rotation_verified="No")), FAIL)
		# no tolerance: the inspector decides, unless an answer is "No"
		self.assertIsNone(evaluate_pmg(frappe._dict(row, tolerance_psi=0)))
		self.assertEqual(evaluate_pmg(frappe._dict(row, tolerance_psi=0, nameplate_verified="No")), FAIL)

	def test_hose_evaluation(self):
		row = frappe._dict(
			crimp_min=0.990,
			crimp_max=1.010,
			test_pressure_spec=6000,
			hold_spec_min=10,
			crimp_a=1.000,
			crimp_b=1.005,
			pressure_reached=6050,
			hold_actual_min=10,
			leak_check="No Leak",
		)
		self.assertEqual(evaluate_hose(row), PASS)
		self.assertEqual(crimp_status(row), "In Spec")
		# one end out of spec fails at once, before the pressure test is entered
		early = frappe._dict(row, crimp_b=1.020, pressure_reached=0, leak_check=None)
		self.assertEqual(crimp_status(early), "Out of Spec")
		self.assertEqual(evaluate_hose(early), FAIL)
		self.assertEqual(crimp_status(frappe._dict(row, crimp_b=0)), "")
		self.assertEqual(evaluate_hose(frappe._dict(row, crimp_b=1.020)), FAIL)
		self.assertEqual(evaluate_hose(frappe._dict(row, pressure_reached=5900)), FAIL)
		self.assertEqual(evaluate_hose(frappe._dict(row, hold_actual_min=9.5)), FAIL)
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
						"default_hold_time_min": 10,
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
			for child in (
				"QC PMG Test",
				"QC Device Test",
				"QC Accumulator Test",
				"QC Proof Test",
				"QC Coating Layer",
			):
				frappe.db.delete(child, {"parent": ("in", names)})
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
		self.assertEqual(unit.hoses[0].hold_time_min, 10)
		self.assertEqual([s.name for s in get_stages(HOSE_WO)], ["_T Hose Test", "_T Hose Release"])
		good = {
			"crimp_a": 1.0,
			"crimp_b": 1.0,
			"pressure_reached": 6100,
			"hold_actual_min": 10,
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
			"hold_actual_min": 10,
			"leak_check": "No Leak",
		}
		doc = self.make("_T Hose Test", unit=HOSE_WO, hose_values={"_TH-1": good, "_TH-2": good})
		self.assertTrue(
			all(h.instrument == "_T-G1" and h.crimp_instrument == "_T-CAL" for h in doc.hose_tests)
		)

	def set_pmgs(self, groups, tolerance=None, **kw):
		unit = frappe.get_doc("QC Unit", WO)
		unit.update(kw)
		unit.setting_tolerance_psi = tolerance
		unit.set("pump_motor_groups", groups)
		unit.save()
		return unit

	def test_pmg_tags_and_limit(self):
		unit = self.set_pmgs(
			[{"relief_setting_psi": 3000}, {"pmg_tag": "pilot", "relief_setting_psi": 1000}, {}]
		)
		self.assertEqual([g.pmg_tag for g in unit.pump_motor_groups], ["PMG-1", "PILOT", "PMG-3"])
		self.assertEqual(unit.pmg_count, 3)
		with self.assertRaises(frappe.ValidationError):
			self.set_pmgs([{} for _ in range(11)])
		with self.assertRaises(frappe.ValidationError):
			self.set_pmgs([{"pmg_tag": "A"}, {"pmg_tag": "a"}])

	def test_legacy_motor_fields_copied_to_pmg1(self):
		unit = self.set_pmgs([], motor_hp=30, pump_type="Variable Piston")
		self.assertEqual(len(unit.pump_motor_groups), 1)
		self.assertEqual(unit.pump_motor_groups[0].motor_hp, 30)
		self.assertEqual(unit.pump_motor_groups[0].pump_type, "Variable Piston")
		unit = self.set_pmgs([], motor_hp=0, pump_type="PV270 axial piston")
		self.assertIn("PV270", unit.pump_motor_groups[0].notes)

	def test_pmg_tests_loaded_evaluated_and_failed(self):
		self.set_pmgs(
			[
				{"relief_setting_psi": 3000, "compensator_setting_psi": 2800, "pump_type": "Variable Piston"},
				{"relief_setting_psi": 2500, "pump_type": "Gear"},
			],
			tolerance=50,
		)
		frappe.db.set_value("QC Stage", "_T Test", "pmg_test", 1)
		try:
			self.make("_T Assembly")
			doc = self.make("_T Test", reading=3000, submit=False)
			self.assertEqual([g.pmg_tag for g in doc.pmg_tests], ["PMG-1", "PMG-2"])
			self.assertEqual(doc.pmg_tests[0].compensator_spec, 2800)
			with self.assertRaises(frappe.ValidationError):
				doc.submit()  # PMG entries missing
			doc.reload()
			for g, relief, comp in ((doc.pmg_tests[0], 3010, 2790), (doc.pmg_tests[1], 2600, 0)):
				g.update(
					{
						"nameplate_verified": "Yes",
						"rotation_verified": "Yes",
						"relief_as_set": relief,
						"compensator_as_set": comp,
					}
				)
			doc.pmg_tests[1].finding = "Relief set high"
			doc.save()
			self.assertEqual([g.result for g in doc.pmg_tests], [PASS, FAIL])
			self.assertEqual(doc.pmg_tests[0].instrument, "_T-G1")
			doc.submit()
			self.assertEqual(doc.status, "Rejected")
			self.assertEqual(
				frappe.db.get_value("Non Conformance", doc.non_conformance, "severity"), "Critical"
			)
		finally:
			frappe.db.set_value("QC Stage", "_T Test", "pmg_test", 0)

	def test_unit_order_documents_and_theoretical_flow(self):
		unit = self.set_pmgs([{"displacement": 80, "displacement_uom": "cc/rev", "motor_rpm": 1780}])
		self.assertEqual(len(unit.construction_documents), 18)
		self.assertEqual(len(unit.quality_documents), 10)
		self.assertAlmostEqual(unit.pump_motor_groups[0].design_flow_gpm, 37.62, places=2)
		unit.append("circuit_devices", {"pmg_tag": "PMG-9", "description": "PRV"})
		with self.assertRaises(frappe.ValidationError):
			unit.save()

	def test_circuit_devices_accumulators_and_proof(self):
		unit = self.set_pmgs([{"relief_setting_psi": 3000}], tolerance=50)
		unit.append(
			"circuit_devices", {"pmg_tag": "pmg-1", "description": "PRV-1", "design_setting": "1500 psi"}
		)
		unit.append("accumulators", {"pmg_tag": "PMG-1", "description": "ACC-1", "precharge_psi": 1000})
		unit.append("proof_test_items", {"description": "Manifold MF-1", "p1_psi": 4500})
		unit.save()
		for flag in ("pmg_test", "proof_test"):
			frappe.db.set_value("QC Stage", "_T Test", flag, 1)
		try:
			self.make("_T Assembly")
			doc = self.make("_T Test", reading=3000, submit=False)
			self.assertEqual([r.description for r in doc.device_tests], ["PRV-1"])
			self.assertEqual(doc.accumulator_tests[0].precharge_spec, 1000)
			self.assertEqual(doc.proof_tests[0].p1_spec, 4500)
			doc.pmg_tests[0].update(
				{"nameplate_verified": "Yes", "rotation_verified": "Yes", "relief_as_set": 3000}
			)
			doc.device_tests[0].update({"as_set": "1500 psi", "result": PASS})
			doc.accumulator_tests[0].precharge_actual = 1010
			doc.proof_tests[0].update(
				{
					"p1_psi": 4300,
					"p1_media": "Hydraulic Oil",
					"p1_duration_min": 5,
					"leak_check": "No Leak",
					"finding": "Pump could not reach proof pressure",
				}
			)
			doc.save()
			self.assertEqual(doc.accumulator_tests[0].result, PASS)
			self.assertEqual(doc.accumulator_tests[0].instrument, "_T-G1")
			self.assertEqual(doc.proof_tests[0].result, FAIL)
			doc.submit()
			self.assertEqual(doc.status, "Rejected")
			self.assertEqual(
				frappe.db.get_value("Non Conformance", doc.non_conformance, "severity"), "Critical"
			)
		finally:
			for flag in ("pmg_test", "proof_test"):
				frappe.db.set_value("QC Stage", "_T Test", flag, 0)

	def test_coating_record_required(self):
		frappe.db.set_value("QC Stage", "_T Assembly", "coating_record", 1)
		try:
			doc = self.make("_T Assembly", submit=False)
			self.assertEqual(len(doc.coating_layers), 5)
			with self.assertRaises(frappe.ValidationError):
				doc.submit()  # layers not marked
			doc.reload()
			for row in doc.coating_layers:
				row.applied = "N/A"
			doc.coating_layers[1].update(
				{
					"applied": "Yes",
					"product_type": "Epoxy",
					"brand": "B",
					"product_code": "X1",
					"mil_thickness": 3,
				}
			)
			doc.save()
			doc.submit()
			self.assertEqual(doc.status, "Accepted")
		finally:
			frappe.db.set_value("QC Stage", "_T Assembly", "coating_record", 0)

	def test_document_templates(self):
		names = ("_T HPU Quality Docs", "_T HPU Quality Docs 2")
		try:
			self.check_document_templates()
		finally:
			for name in names:
				frappe.delete_doc("QC Document Template", name, force=1, ignore_missing=True)
			unit = frappe.get_doc("QC Unit", WO)
			unit.quality_document_template = None
			unit.construction_document_template = None
			unit.set("quality_documents", [])
			unit.set("construction_documents", [])
			unit.save()

	def check_document_templates(self):
		tmpl = frappe.get_doc(
			{
				"doctype": "QC Document Template",
				"template_name": "_T HPU Quality Docs",
				"category": "Quality",
				"product_type": "Power Unit",
				"is_default": 1,
				"documents": [
					{"document": "Material Test Reports", "required": "Yes"},
					{"document": "Hydrostatic Test Chart", "required": "Yes", "reference": "QP-12"},
				],
			}
		).insert()
		unit = frappe.get_doc("QC Unit", WO)
		unit.set("quality_documents", [])
		unit.quality_document_template = None
		unit.save()
		self.assertEqual(unit.quality_document_template, tmpl.name)
		self.assertEqual(
			[r.document for r in unit.quality_documents], ["Material Test Reports", "Hydrostatic Test Chart"]
		)
		self.assertEqual(unit.quality_documents[1].reference, "QP-12")
		# a second default for the same category and product type replaces the first
		frappe.get_doc(
			{
				"doctype": "QC Document Template",
				"template_name": "_T HPU Quality Docs 2",
				"category": "Quality",
				"product_type": "Power Unit",
				"is_default": 1,
				"documents": [{"document": "Certificate of Conformance"}],
			}
		).insert()
		self.assertEqual(frappe.db.get_value("QC Document Template", tmpl.name, "is_default"), 0)
		# a quality template cannot be used for the construction list
		unit.reload()
		unit.construction_document_template = tmpl.name
		unit.set("construction_documents", [])
		with self.assertRaises(frappe.ValidationError):
			unit.save()

	def test_hose_customer_spec(self):
		unit = self.make_hose_unit()
		unit.hoses[0].update(
			{
				"spec_basis": "Customer Spec",
				"spec_reference": "CUST-HS-100 Rev C",
				"customer_test_pressure_psi": 7500,
				"customer_crimp_diameter": 1.05,
				"customer_hold_time_min": 15,
			}
		)
		unit.save()
		spec = hose_spec(unit.hoses[0])
		self.assertEqual(spec.basis, "Customer Spec")
		self.assertEqual(spec.test_pressure, 7500)
		self.assertEqual(spec.crimp_diameter, 1.05)
		self.assertEqual(spec.crimp_tolerance, 0.01)  # blank customer tolerance: PSIF value applies
		self.assertEqual(spec.hold_min, 15)
		rows = {r["hose_tag"]: r for r in build_hose_tests(HOSE_WO)}
		self.assertEqual(rows["_TH-1"]["crimp_min"], 1.04)
		self.assertEqual(rows["_TH-1"]["spec_reference"], "CUST-HS-100 Rev C")
		self.assertEqual(rows["_TH-2"]["spec_basis"], "PSIF Standard")
		self.assertEqual(rows["_TH-2"]["test_pressure_spec"], 6000)
		# customer spec needs a reference
		unit.hoses[0].spec_reference = ""
		with self.assertRaises(frappe.ValidationError):
			unit.save()

	def test_out_of_spec_crimp_links_nc(self):
		self.make_hose_unit()
		good = {
			"crimp_a": 1.0,
			"crimp_b": 1.0,
			"pressure_reached": 6100,
			"hold_actual_min": 10,
			"leak_check": "No Leak",
		}
		bad = dict(good, crimp_b=1.03, finding="End B over-crimped")
		doc = self.make("_T Hose Test", unit=HOSE_WO, hose_values={"_TH-1": good, "_TH-2": bad})
		rows = {h.hose_tag: h for h in doc.hose_tests}
		self.assertEqual(rows["_TH-2"].crimp_status, "Out of Spec")
		self.assertEqual(rows["_TH-2"].result, FAIL)
		self.assertTrue(doc.non_conformance)
		self.assertEqual(
			frappe.db.get_value("QC Hose Test", rows["_TH-2"].name, "non_conformance"), doc.non_conformance
		)
		self.assertFalse(frappe.db.get_value("QC Hose Test", rows["_TH-1"].name, "non_conformance"))
		details = frappe.db.get_value("Non Conformance", doc.non_conformance, "details")
		self.assertIn("Out of Spec", details)

	def test_dash_size_and_crimp_warning(self):
		self.assertEqual(normalise_dash("12"), ("-12", 0.75))
		self.assertEqual(normalise_dash("-8"), ("-8", 0.5))
		self.assertEqual(normalise_dash("custom"), ("custom", 0.0))
		hose = frappe._dict(hose_tag="0001", hose_size="-12", nominal_id_in=0.75)
		self.assertIsNone(
			crimp_diameter_warning(frappe._dict(hose, crimp_diameter_spec=1.21), "crimp_diameter_spec")
		)
		self.assertTrue(
			crimp_diameter_warning(frappe._dict(hose, crimp_diameter_spec=12.002), "crimp_diameter_spec")
		)
		self.assertTrue(
			crimp_diameter_warning(frappe._dict(hose, crimp_diameter_spec=0.5), "crimp_diameter_spec")
		)

	def test_stage_rows_before_first_save(self):
		self.make_hose_unit()
		tables = get_stage_test_rows(HOSE_WO, "_T Hose Test")
		self.assertEqual(sorted(r["hose_tag"] for r in tables["hose_tests"]), ["_TH-1", "_TH-2"])
		self.assertEqual(tables["hose_tests"][0]["spec_basis"], "PSIF Standard")
		self.assertEqual(tables["pmg_tests"], [])
