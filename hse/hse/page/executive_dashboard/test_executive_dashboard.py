# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from hse.hse.page.executive_dashboard.executive_dashboard import get_dashboard, pillar_status


class UnitTestPillarStatus(UnitTestCase):
	def test_status_follows_worst_item(self):
		self.assertEqual(pillar_status([]), "ok")
		self.assertEqual(pillar_status([{"level": "info"}]), "ok")
		self.assertEqual(pillar_status([{"level": "info"}, {"level": "warning"}]), "watch")
		self.assertEqual(pillar_status([{"level": "warning"}, {"level": "danger"}]), "action")


class IntegrationTestExecutiveDashboard(IntegrationTestCase):
	def test_get_dashboard_returns_sections(self):
		frappe.set_user("Administrator")
		data = get_dashboard("bogus")
		self.assertEqual(data["period"]["key"], "this_month")
		for key in ("safety", "training", "quality", "metrics", "reviews"):
			self.assertIn(key, data)
		self.assertIn(data["safety"]["status"], ("ok", "watch", "action"))
		groups = [g["group"] for g in data["metrics"]]
		self.assertTrue(set(groups) <= {"Safety", "Training", "Quality"})
		self.assertIsNotNone(data["training"])
		self.assertIn(data["training"]["status"], ("ok", "watch", "action"))
