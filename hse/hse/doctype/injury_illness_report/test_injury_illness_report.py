# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import UnitTestCase

from hse.hse.doctype.injury_illness_report.injury_illness_report import (
	Injury_IllnessReport,
	apply_cap,
	corrective_action_summary,
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

	def test_signature_needs_completed_by(self):
		doc = frappe._dict(completed_by_signature="data:image/png;base64,AAAA")
		with self.assertRaises(frappe.ValidationError):
			Injury_IllnessReport.validate_sign_off(doc)

	def test_signing_dates_the_report(self):
		doc = frappe._dict(completed_by="EMP-0001", completed_by_signature="data:image/png;base64,AAAA")
		Injury_IllnessReport.validate_sign_off(doc)
		self.assertTrue(doc.completed_by_date)
		doc.completed_by_date = "2026-10-29"
		Injury_IllnessReport.validate_sign_off(doc)
		self.assertEqual(doc.completed_by_date, "2026-10-29")  # an entered date is kept
		Injury_IllnessReport.validate_sign_off(frappe._dict())  # unsigned is fine

	def test_corrective_action_summary(self):
		from datetime import date

		row = frappe._dict
		self.assertEqual(corrective_action_summary([]), (None, None))
		actions = [
			row(date_due="2026-11-20", date_done="2026-11-10"),
			row(date_due="2026-12-01"),
			row(date_due="2026-11-25"),
		]
		# open actions: earliest open due date, not the completed one's
		self.assertEqual(corrective_action_summary(actions), (date(2026, 11, 25), None))
		actions[1].date_done, actions[2].date_done = "2026-11-28", "2026-11-21"
		self.assertEqual(corrective_action_summary(actions), (None, date(2026, 11, 28)))
		# an open action without a due date is not overdue, but the report is not complete
		self.assertEqual(corrective_action_summary([row()]), (None, None))
