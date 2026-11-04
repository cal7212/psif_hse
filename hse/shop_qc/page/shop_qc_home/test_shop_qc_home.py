# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hse.shop_qc.page.shop_qc_home.shop_qc_home import find_work_order, get_home


class IntegrationTestShopQCHome(IntegrationTestCase):
	def test_get_home_returns_sections(self):
		frappe.set_user("Administrator")
		data = get_home("last_90_days")
		for key in (
			"period",
			"shops",
			"pipeline",
			"attention",
			"stage_yield",
			"recent",
			"my_drafts",
			"metrics",
			"reviews",
		):
			self.assertIn(key, data)
		self.assertEqual(len(data["pipeline"]["steps"]), 6)

	def test_unknown_shop_is_ignored(self):
		frappe.set_user("Administrator")
		self.assertIsNone(get_home("this_month", "No Such Shop")["shop"])

	def test_blank_work_order_finds_nothing(self):
		frappe.set_user("Administrator")
		self.assertEqual(find_work_order("  "), [])
