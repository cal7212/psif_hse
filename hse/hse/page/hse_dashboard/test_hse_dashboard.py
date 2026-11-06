# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hse.hse.page.hse_dashboard.hse_dashboard import get_dashboard
from hse.quality_metrics.metrics import METRICS, calculate

INCIDENT_METRICS = (
	"incidents_reported",
	"recordable_cases",
	"days_away_cases",
	"near_miss_reports",
	"incidents_open",
	"incident_actions_overdue",
	"incident_actions_on_time_pct",
	"days_since_recordable",
)


class IntegrationTestHSEDashboard(IntegrationTestCase):
	def test_get_dashboard_returns_sections(self):
		frappe.set_user("Administrator")
		data = get_dashboard("last_90_days")
		for key in (
			"user",
			"today",
			"period",
			"periods",
			"headline",
			"attention",
			"incidents",
			"recent",
			"my_drafts",
			"metrics",
			"reviews",
		):
			self.assertIn(key, data)
		self.assertEqual(data["period"]["key"], "last_90_days")
		self.assertIsInstance(data["headline"], list)
		self.assertIsInstance(data["recent"], list)
		levels = [a["level"] for a in data["attention"]]
		order = {"danger": 0, "warning": 1, "info": 2}
		self.assertEqual(levels, sorted(levels, key=lambda lvl: order.get(lvl, 9)))

	def test_bogus_period_falls_back(self):
		frappe.set_user("Administrator")
		self.assertEqual(get_dashboard("bogus")["period"]["key"], "this_month")

	def test_incident_metrics_registered_and_empty_period(self):
		for key in INCIDENT_METRICS:
			self.assertIn(key, METRICS)
		for key in ("incidents_reported", "recordable_cases", "days_away_cases", "near_miss_reports"):
			value, _detail = calculate(key, "2001-01-01", "2001-01-31")
			self.assertEqual(value, 0, key)
		value, _detail = calculate("incident_actions_on_time_pct", "2001-01-01", "2001-01-31")
		self.assertIsNone(value)
