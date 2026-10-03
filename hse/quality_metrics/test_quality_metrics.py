# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from datetime import date, timedelta

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import now_datetime

from hse.quality_metrics.metrics import (
	AT_LEAST,
	AT_MOST,
	FAILED,
	OPEN,
	PASSED,
	RECORD_ONLY,
	calculate,
	evaluate,
	get_review_period,
	target_text,
)

PROC = "_Test Quality Metrics Procedure"
GOAL = "_Test NC Metrics Goal"


class UnitTestQualityMetrics(UnitTestCase):
	def test_monthly_period_is_previous_month(self):
		self.assertEqual(get_review_period("Monthly", "2026-10-01"), (date(2026, 9, 1), date(2026, 9, 30)))
		self.assertEqual(get_review_period(None, "2026-03-15"), (date(2026, 2, 1), date(2026, 2, 28)))

	def test_weekly_period_is_previous_mon_to_sun(self):
		# 2026-10-01 is a Thursday
		self.assertEqual(get_review_period("Weekly", "2026-10-01"), (date(2026, 9, 21), date(2026, 9, 27)))

	def test_quarterly_and_daily(self):
		self.assertEqual(get_review_period("Quarterly", "2026-10-01"), (date(2026, 7, 1), date(2026, 9, 30)))
		self.assertEqual(get_review_period("Daily", "2026-10-01"), (date(2026, 9, 30), date(2026, 9, 30)))

	def test_evaluate(self):
		self.assertEqual(evaluate(92, AT_LEAST, 90), PASSED)
		self.assertEqual(evaluate(88, AT_LEAST, 90), FAILED)
		self.assertEqual(evaluate(0, AT_MOST, 0), PASSED)
		self.assertEqual(evaluate(1, AT_MOST, 0), FAILED)
		self.assertEqual(evaluate(None, AT_LEAST, 90), OPEN)
		self.assertEqual(evaluate(None, RECORD_ONLY, 0), PASSED)

	def test_target_text(self):
		self.assertEqual(target_text(AT_LEAST, 90, "Percent"), "≥ 90%")
		self.assertEqual(target_text(AT_MOST, 14, "Day"), "≤ 14 Day")
		self.assertEqual(target_text(AT_MOST, 0, "Nos"), "≤ 0")


class IntegrationTestQualityMetrics(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Quality Procedure", PROC):
			frappe.get_doc({"doctype": "Quality Procedure", "quality_procedure_name": PROC}).insert()

	def make_nc(self, severity="Critical", days_old=0, status="Open"):
		nc = frappe.get_doc(
			{
				"doctype": "Non Conformance",
				"subject": f"_Test metrics NC {frappe.generate_hash(length=6)}",
				"procedure": PROC,
				"status": "Open",
				"severity": severity,
			}
		).insert()
		if days_old:
			frappe.db.set_value(
				"Non Conformance",
				nc.name,
				"creation",
				now_datetime() - timedelta(days=days_old),
				update_modified=False,
			)
		if status != "Open":
			nc.reload()
			nc.status = status
			nc.save()
		return nc

	def test_resolved_on_stamped_and_cleared(self):
		nc = self.make_nc(severity="Low", status="Resolved")
		self.assertTrue(nc.resolved_on)
		nc.status = "Open"
		nc.save()
		self.assertFalse(nc.resolved_on)

	def test_open_critical_metric(self):
		nc = self.make_nc(days_old=10)
		value, detail = calculate("nc_open_critical_over_7_days", "2000-01-01", "2000-01-31")
		self.assertGreaterEqual(value, 1)
		self.assertIn(nc.name, detail)

	def test_review_calculates_and_failed_review_creates_action(self):
		self.make_nc(days_old=10)
		if frappe.db.exists("Quality Goal", GOAL):
			frappe.delete_doc("Quality Goal", GOAL, force=1)
		goal = frappe.get_doc(
			{
				"doctype": "Quality Goal",
				"goal": GOAL,
				"frequency": "None",
				"objectives": [
					{
						"hse_metric": "nc_open_critical_over_7_days",
						"target_operator": AT_MOST,
						"target_value": 0,
					},
					{"hse_metric": "nc_opened", "target_operator": RECORD_ONLY},
				],
			}
		).insert()
		self.assertEqual(goal.objectives[0].target, "≤ 0")
		self.assertTrue(goal.objectives[0].objective)

		review = frappe.get_doc({"doctype": "Quality Review", "goal": GOAL, "date": "2026-10-01"}).insert()
		self.assertEqual(str(review.period_start), "2026-09-01")
		self.assertEqual(str(review.period_end), "2026-09-30")
		rows = {r.hse_metric: r for r in review.reviews}
		self.assertEqual(rows["nc_open_critical_over_7_days"].status, FAILED)
		self.assertEqual(rows["nc_opened"].status, PASSED)
		self.assertEqual(review.status, FAILED)
		self.assertTrue(review.metrics_calculated_on)

		action = frappe.db.get_value(
			"Quality Action", {"review": review.name}, ["name", "corrective_preventive"]
		)
		self.assertTrue(action)
		self.assertEqual(action[1], "Corrective")

		# Saving again does not create a second action
		review.save()
		self.assertEqual(frappe.db.count("Quality Action", {"review": review.name}), 1)


class IntegrationTestStarterGoalsButton(IntegrationTestCase):
	def test_button_creates_missing_goals_once(self):
		from hse.quality_metrics.events import create_starter_goals, get_missing_starter_goals
		from hse.quality_metrics.starter_goals import STARTER_GOALS

		names = [g["goal"] for g in STARTER_GOALS]
		for n in names:
			if frappe.db.exists("Quality Goal", n):
				frappe.delete_doc("Quality Goal", n, force=1)
		self.assertEqual(sorted(get_missing_starter_goals()), sorted(names))

		result = create_starter_goals()
		self.assertEqual(sorted(result["created"]), sorted(names))
		self.assertEqual(get_missing_starter_goals(), [])
		goal = frappe.get_doc("Quality Goal", "Housekeeping")
		self.assertEqual(goal.frequency, "Monthly")
		self.assertTrue(all(o.hse_metric for o in goal.objectives))

		again = create_starter_goals()
		self.assertEqual(again["created"], [])
		self.assertEqual(sorted(again["existing"]), sorted(names))

	def test_button_requires_quality_role(self):
		from hse.quality_metrics.events import create_starter_goals

		user = "test-no-quality-role@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				{"doctype": "User", "email": user, "first_name": "No Quality Role", "send_welcome_email": 0}
			).insert()
		frappe.set_user(user)
		try:
			with self.assertRaises(frappe.PermissionError):
				create_starter_goals()
		finally:
			frappe.set_user("Administrator")
