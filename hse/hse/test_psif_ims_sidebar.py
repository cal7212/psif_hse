# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

LEFT_OUT = {"Depreciation Schedule", "Asset Capitalization", "Asset Value Adjustment"}


class TestPSIFIMSSidebar(IntegrationTestCase):
	def test_installed_as_standard(self):
		doc = frappe.get_doc("Sidebar", "PSIF IMS")
		self.assertEqual(doc.module, "HSE")
		self.assertEqual(doc.app, "hse")
		self.assertTrue(doc.standard)

	def test_links_resolve(self):
		doc = frappe.get_doc("Sidebar", "PSIF IMS")
		for row in doc.items:
			if row.type != "Link" or row.link_type == "Workspace":
				# The HSE workspace is site content, not shipped by the app.
				continue
			self.assertTrue(frappe.db.exists(row.link_type, row.link_to), f"{row.link_type} {row.link_to}")

	def test_dashboards_first_and_no_accounting_pages(self):
		doc = frappe.get_doc("Sidebar", "PSIF IMS")
		links = [row.link_to for row in doc.items if row.type == "Link"]
		self.assertEqual(
			links[:5],
			[
				"executive-dashboard",
				"hse-dashboard",
				"training-dashboard",
				"shop-qc-home",
				"maintenance-dashboard",
			],
		)
		self.assertFalse(LEFT_OUT & set(links))
		# HSE Home is retired; only its redirect stub remains.
		self.assertNotIn("hse-home", links)
		self.assertEqual(doc.title, "PSIF IMS")
		self.assertFalse([link for link in links if "Depreciation" in (link or "")])
