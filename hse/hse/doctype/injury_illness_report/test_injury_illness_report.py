# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import UnitTestCase

from hse.hse.doctype.injury_illness_report.injury_illness_report import (
	apply_cap,
	count_days,
	five_whys_errors,
)


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

	def test_status_editable_after_submit(self):
		self.assertTrue(frappe.get_meta("Injury_Illness Report").get_field("status").allow_on_submit)

	def test_five_whys_optional(self):
		self.assertEqual(five_whys_errors(frappe._dict()), [])
		self.assertEqual(five_whys_errors(frappe._dict(five_whys_problem="Truck struck bollard")), [])

	def test_five_whys_in_order(self):
		doc = frappe._dict(
			five_whys_problem="Truck struck bollard", why_1="Driver did not see it", why_2="No spotter"
		)
		self.assertEqual(five_whys_errors(doc), [])
		doc.why_2, doc.why_3 = "  ", "No backing procedure"
		self.assertEqual(len(five_whys_errors(doc)), 1)  # Why 2 skipped
		self.assertIn("Why 2", five_whys_errors(doc)[0])

	def test_five_whys_need_problem_statement(self):
		errors = five_whys_errors(frappe._dict(why_1="Driver did not see it"))
		self.assertEqual(len(errors), 1)
		self.assertIn("Problem Statement", errors[0])
