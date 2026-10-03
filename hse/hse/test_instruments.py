# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase


class TestInspectionInstruments(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		for iid, itype, due, cal in (
			("_T-IR1", "Insulation Resistance Tester", "2099-12-31", 1),
			("_T-DMM", "Multimeter", "2099-12-31", 1),
			("_T-IROLD", "Insulation Resistance Tester", "2000-01-01", 1),
			("_T-VD", "Voltage Detector", None, 0),
		):
			if not frappe.db.exists("Measuring Instrument", iid):
				frappe.get_doc(
					{
						"doctype": "Measuring Instrument",
						"instrument_id": iid,
						"instrument_type": itype,
						"calibration_due": due,
						"calibration_required": cal,
					}
				).insert()

	def asset_inspection(self, instruments, reading_instrument=None):
		doc = frappe.new_doc("Asset Inspection")
		doc.inspection_date = frappe.utils.now_datetime()
		for i in instruments:
			doc.append("instruments", {"instrument": i})
		doc.append(
			"items",
			{
				"check_item": "Insulation resistance A-G (MΩ)",
				"numeric": 1,
				"min_value": 100,
				"reading_value": 2500,
				"result": "Pass",
				"instrument": reading_instrument,
			},
		)
		doc.sync_instruments()
		return doc

	def test_interval_sets_due_date(self):
		doc = frappe.get_doc(
			{
				"doctype": "Measuring Instrument",
				"instrument_id": "_t-int",
				"instrument_type": "Clamp Meter",
				"last_calibrated": "2026-01-15",
				"calibration_interval_months": 12,
			}
		).insert()
		self.assertEqual(doc.name, "_T-INT")
		self.assertEqual(str(doc.calibration_due), "2027-01-15")

	def test_asset_inspection_single_instrument_fills_reading(self):
		doc = self.asset_inspection(["_T-IR1"])
		self.assertEqual(doc.items[0].instrument, "_T-IR1")
		doc.check_test_equipment()  # no error

	def test_asset_inspection_out_of_cal_blocks(self):
		doc = self.asset_inspection(["_T-IROLD"])
		with self.assertRaises(frappe.ValidationError):
			doc.check_test_equipment()

	def test_asset_inspection_needs_reading_instrument_with_two(self):
		doc = self.asset_inspection(["_T-IR1", "_T-DMM"])
		with self.assertRaises(frappe.ValidationError):
			doc.check_test_equipment()

	def test_verify_only_instrument_allowed_without_due_date(self):
		doc = self.asset_inspection(["_T-VD", "_T-IR1"], reading_instrument="_T-IR1")
		doc.check_test_equipment()  # no error

	def test_numeric_reading_without_equipment_blocks(self):
		doc = self.asset_inspection([])
		with self.assertRaises(frappe.ValidationError):
			doc.check_test_equipment()

	def test_record_only_reading_needs_no_instrument(self):
		doc = frappe.new_doc("Asset Inspection")
		doc.inspection_date = frappe.utils.now_datetime()
		doc.append(
			"items",
			{"check_item": "Odometer at start", "numeric": 1, "reading_value": 48210, "result": "Pass"},
		)
		doc.sync_instruments()
		doc.check_test_equipment()  # no error
		self.assertFalse(doc.instruments)
