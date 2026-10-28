# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import add_days, flt, nowdate

from hse.hse import supplies


class UnitTestShopSupplies(UnitTestCase):
	def test_receipt_row_uses_typed_cost(self):
		row = frappe._dict(item_code="RAG", qty=5, rate=2.5)
		with patch.object(supplies, "current_rate", return_value=9):
			v = supplies.receipt_row(row, "WH")
		self.assertEqual((v["basic_rate"], v["t_warehouse"], v["qty"]), (2.5, "WH", 5))
		self.assertNotIn("allow_zero_valuation_rate", v)

	def test_receipt_row_blank_cost_uses_current_rate(self):
		row = frappe._dict(item_code="RAG", qty=1, rate=None)
		with patch.object(supplies, "current_rate", return_value=3.75):
			self.assertEqual(supplies.receipt_row(row, "WH")["basic_rate"], 3.75)

	def test_receipt_row_no_rate_allows_zero_valuation(self):
		row = frappe._dict(item_code="RAG", qty=1)
		with patch.object(supplies, "current_rate", return_value=0):
			self.assertEqual(supplies.receipt_row(row, "WH")["allow_zero_valuation_rate"], 1)

	def test_receipt_row_rejects_zero_qty(self):
		with self.assertRaises(frappe.ValidationError):
			supplies.receipt_row(frappe._dict(item_code="RAG", qty=0), "WH")

	def test_rows_need_an_item(self):
		with self.assertRaises(frappe.ValidationError):
			supplies._rows('[{"qty": 1}]')

	def test_future_posting_date_rejected(self):
		with self.assertRaisesRegex(frappe.ValidationError, "future"):
			supplies._posting(frappe._dict(), add_days(nowdate(), 3))

	def test_back_dated_posting_sets_posting_time(self):
		doc = frappe._dict()
		supplies._posting(doc, add_days(nowdate(), -2))
		self.assertEqual(doc.set_posting_time, 1)

	def test_serial_item_rejected(self):
		item = frappe._dict(name="X", is_stock_item=1, has_serial_no=1, has_batch_no=0, disabled=0)
		with patch("hse.hse.supplies.frappe.db.get_value", return_value=item):
			with self.assertRaisesRegex(frappe.ValidationError, "serial"):
				supplies._check_item("X")


class IntegrationTestShopSupplies(IntegrationTestCase):
	def test_stock_entry_custom_fields(self):
		meta = frappe.get_meta("Stock Entry")
		for field in ("issued_to", "qc_unit", "qc_work_order"):
			self.assertTrue(meta.has_field(field), field)

	def test_receive_issue_count(self):
		from frappe.tests.utils import make_test_records

		make_test_records("Item")
		item = "_Test Item"
		warehouse = "_Test Warehouse - _TC"
		company = frappe.db.get_value("Warehouse", warehouse, "company")
		if not (frappe.db.exists("Item", item) and company):
			self.skipTest("ERPNext test records are not available")
		frappe.db.set_value("Item", item, {"has_serial_no": 0, "has_batch_no": 0, "is_stock_item": 1})
		start = supplies.on_hand(item, warehouse)

		received = supplies.receive(warehouse, [{"item_code": item, "qty": 10, "rate": 4}], company=company)
		se = frappe.get_doc("Stock Entry", received)
		self.assertEqual((se.docstatus, se.purpose), (1, "Material Receipt"))
		self.assertEqual(flt(se.items[0].basic_rate), 4)
		self.assertEqual(supplies.on_hand(item, warehouse), start + 10)

		issued = supplies.issue(warehouse, [{"item_code": item, "qty": 3}], note="Wipe down", company=company)
		se = frappe.get_doc("Stock Entry", issued)
		self.assertEqual((se.docstatus, se.purpose, se.remarks), (1, "Material Issue", "Wipe down"))
		self.assertEqual(supplies.on_hand(item, warehouse), start + 7)

		self.assertIsNone(supplies.count(warehouse, [{"item_code": item, "qty": start + 7}], company=company))
		counted = supplies.count(warehouse, [{"item_code": item, "qty": start + 5}], company=company)
		self.assertEqual(frappe.db.get_value("Stock Reconciliation", counted, "docstatus"), 1)
		self.assertEqual(supplies.on_hand(item, warehouse), start + 5)
