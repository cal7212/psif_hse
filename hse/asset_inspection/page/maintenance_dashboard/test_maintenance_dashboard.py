# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hse.asset_inspection import purpose as ap
from hse.asset_inspection.page.maintenance_dashboard.maintenance_dashboard import get_dashboard, pillar
from hse.quality_metrics.metrics import METRICS, calculate

NEW_METRICS = (
	"safety_inspection_on_time_pct",
	"maintenance_on_time_pct",
	"safety_inspections_overdue",
	"maintenance_overdue",
	"safety_assets_out_of_service",
	"maintenance_requests_open",
	"asset_repairs_open",
)


class IntegrationTestMaintenanceDashboard(IntegrationTestCase):
	def test_get_dashboard_returns_sections(self):
		frappe.set_user("Administrator")
		data = get_dashboard("last_90_days")
		for key in (
			"headline",
			"attention",
			"overdue",
			"coming_due",
			"by_category",
			"repairs",
			"out_of_service",
			"requests",
			"inspections",
			"metrics",
			"reviews",
		):
			self.assertIn(key, data)
		self.assertEqual(data["period"]["key"], "last_90_days")
		self.assertIsInstance(data["headline"], list)
		self.assertTrue(data["metrics"])
		for row in data["overdue"] + data["coming_due"]:
			self.assertEqual(row["doctype"], "Asset Maintenance Log")

	def test_bogus_period_falls_back(self):
		frappe.set_user("Administrator")
		self.assertEqual(get_dashboard("bogus")["period"]["key"], "this_month")

	def test_pillar(self):
		frappe.set_user("Administrator")
		p = pillar()
		self.assertIn("summary", p)
		self.assertIn("maintenance_overdue", p["summary"])

	def test_new_metrics_registered(self):
		for key in NEW_METRICS:
			self.assertIn(key, METRICS)
			calculate(key, "2001-01-01", "2001-01-31")

	def test_safety_split_adds_up(self):
		"""Safety plus maintenance overdue equals the combined overdue count."""
		from hse.hse.page.hse_home.hse_home import _logs_overdue

		combined = {r.name for r in _logs_overdue(None)}
		safety = {r.name for r in _logs_overdue(ap.SAFETY)}
		maint = {r.name for r in _logs_overdue(ap.MAINTENANCE)}
		self.assertFalse(safety & maint)
		self.assertEqual(safety | maint, combined)


class UnitTestPurpose(IntegrationTestCase):
	def test_category_decides(self):
		cat = ap.safety_category()
		self.assertEqual(ap.purpose_of(cat, None, {}), ap.SAFETY)
		self.assertEqual(ap.purpose_of("Building Systems", None, {}), ap.MAINTENANCE)
		self.assertEqual(ap.purpose_of(None, None, {}), ap.MAINTENANCE)

	def test_template_override_wins(self):
		cat = ap.safety_category()
		overrides = {"Forklift": ap.SAFETY, "Vent": ap.MAINTENANCE}
		self.assertEqual(ap.purpose_of("Building Systems", "Forklift", overrides), ap.SAFETY)
		self.assertEqual(ap.purpose_of(cat, "Vent", overrides), ap.MAINTENANCE)
		self.assertEqual(ap.purpose_of("Building Systems", "Other", overrides), ap.MAINTENANCE)
