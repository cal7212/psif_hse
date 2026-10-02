# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.tests import UnitTestCase

from hse.hse.doctype.injury_illness_report.injury_illness_report import apply_cap, count_days


class UnitTestInjury_IllnessReport(UnitTestCase):
	def test_start_on_injury_date_skips_that_day(self):
		# injured 9/14, back 9/16 -> only 9/15 counts
		self.assertEqual(count_days("2026-09-14", "2026-09-16", "2026-09-14"), 1)

	def test_start_day_after_injury(self):
		self.assertEqual(count_days("2026-09-15", "2026-09-16", "2026-09-14"), 1)

	def test_weekend_included_and_no_incident_date(self):
		self.assertEqual(count_days("2026-09-11", "2026-09-14"), 3)

	def test_incomplete_or_reversed(self):
		self.assertEqual(count_days("2026-09-15", None, "2026-09-14"), 0)
		self.assertEqual(count_days("2026-09-15", "2026-09-10"), 0)

	def test_cap_180(self):
		self.assertEqual(apply_cap([150, 50, 10]), [150, 30, 0])
