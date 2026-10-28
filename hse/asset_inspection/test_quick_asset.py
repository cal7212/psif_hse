# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import add_days, flt, nowdate

from hse.asset_inspection.quick_asset import (
	EXISTING_ASSET,
	SETTINGS,
	build_asset_values,
	create_asset,
	get_asset_item,
	placeholder_amount,
)

ITEM = {"name": "_T-ASSET-01", "item_name": "Test Fire Extinguisher", "asset_category": "_T Category"}


class UnitTestQuickAsset(UnitTestCase):
	def test_values_skip_purchase_details(self):
		v = build_asset_values(ITEM, "", "Fab Shop", "2026-01-15", "_T Co", 0.5)
		self.assertEqual(v["asset_type"], EXISTING_ASSET)
		self.assertEqual(v["calculate_depreciation"], 0)
		self.assertEqual(v["asset_name"], "Test Fire Extinguisher")  # falls back to the item name
		self.assertEqual((v["purchase_date"], v["available_for_use_date"]), ("2026-01-15", "2026-01-15"))
		self.assertEqual(v["net_purchase_amount"], 0.5)
		self.assertNotIn("purchase_receipt", v)
		self.assertNotIn("purchase_invoice", v)
		self.assertNotIn("custodian", v)

	def test_values_keep_optional_fields(self):
		v = build_asset_values(ITEM, " Ext 12 ", "Fab Shop", "2026-01-15", "_T Co", 1, "EMP-1", "Shop", 1)
		self.assertEqual(v["asset_name"], "Ext 12")
		self.assertEqual((v["custodian"], v["department"], v["maintenance_required"]), ("EMP-1", "Shop", 1))


class IntegrationTestQuickAsset(IntegrationTestCase):
	def test_placeholder_uses_setting_then_field_default(self):
		saved = frappe.db.get_single_value(SETTINGS, "placeholder_purchase_amount")
		try:
			frappe.db.set_single_value(SETTINGS, "placeholder_purchase_amount", 2.5)
			self.assertEqual(placeholder_amount(), 2.5)
			frappe.db.set_single_value(SETTINGS, "placeholder_purchase_amount", None)
			default = frappe.get_meta(SETTINGS).get_field("placeholder_purchase_amount").default
			self.assertEqual(placeholder_amount(), flt(default))
			self.assertGreater(placeholder_amount(), 0)
		finally:
			frappe.db.set_single_value(SETTINGS, "placeholder_purchase_amount", saved)

	def test_stock_item_is_rejected(self):
		code = "_T-HSE-STOCK-ITEM"
		if not frappe.db.exists("Item", code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": code,
					"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name")
					or "All Item Groups",
					"stock_uom": frappe.db.get_value("UOM", {}, "name"),
					"is_stock_item": 1,
				}
			).insert()
		with self.assertRaises(frappe.ValidationError):
			get_asset_item(code)

	def test_future_in_service_date_is_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "future"):
			create_asset("X", "Anywhere", add_days(nowdate(), 5), company="Any", item_code="Any")
