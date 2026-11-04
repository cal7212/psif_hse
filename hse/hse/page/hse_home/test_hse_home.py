# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from datetime import date

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from hse.hse.page.hse_home.hse_home import get_home, period_bounds


class UnitTestHSEHomePeriods(UnitTestCase):
	def test_this_month(self):
		self.assertEqual(period_bounds("this_month", "2026-11-03"), (date(2026, 11, 1), date(2026, 11, 3)))

	def test_last_month(self):
		self.assertEqual(period_bounds("last_month", "2026-03-15"), (date(2026, 2, 1), date(2026, 2, 28)))

	def test_last_month_across_year(self):
		self.assertEqual(period_bounds("last_month", "2026-01-10"), (date(2025, 12, 1), date(2025, 12, 31)))

	def test_last_90_days(self):
		start, end = period_bounds("last_90_days", "2026-11-03")
		self.assertEqual((end - start).days, 89)

	def test_year_to_date(self):
		self.assertEqual(period_bounds("year_to_date", "2026-11-03"), (date(2026, 1, 1), date(2026, 11, 3)))

	def test_unknown_defaults_to_this_month(self):
		self.assertEqual(period_bounds("bogus", "2026-11-03"), (date(2026, 11, 1), date(2026, 11, 3)))


class IntegrationTestHSEHome(IntegrationTestCase):
	def test_get_home_returns_sections(self):
		frappe.set_user("Administrator")
		data = get_home("this_month")
		for key in (
			"user",
			"today",
			"period",
			"periods",
			"safety",
			"attention",
			"my_work",
			"metrics",
			"reviews",
		):
			self.assertIn(key, data)
		self.assertIsInstance(data["attention"], list)


class UnitTestOverdueRange(UnitTestCase):
	def test_range_ends_yesterday(self):
		from frappe.utils import add_days, getdate

		from hse.hse.page.hse_home.hse_home import overdue_range

		start, end = overdue_range()
		self.assertEqual(end, str(add_days(getdate(), -1)))
		self.assertLess(start, end)
