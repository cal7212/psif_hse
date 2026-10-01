# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.tests import IntegrationTestCase, UnitTestCase

from hse.housekeeping_inspection.doctype.housekeeping_inspection.housekeeping_inspection import summarize
from hse.housekeeping_inspection.utils import next_due, schedule_status_for, trip_status


def row(result, critical=0, corrected=0):
	return {"result": result, "is_critical": critical, "corrected_on_spot": corrected}


class UnitTestHousekeepingInspection(UnitTestCase):
	"""Pure logic tests; no database needed."""

	def test_all_pass_accepted(self):
		s = summarize([row("Pass")] * 10, 90)
		self.assertEqual((s.status, s.score, s.severity), ("Accepted", 100.0, None))

	def test_na_excluded_from_score(self):
		s = summarize([row("Pass")] * 9 + [row("N/A")], 90)
		self.assertEqual((s.items_checked, s.score), (9, 100.0))

	def test_open_critical_fail_is_critical(self):
		s = summarize([row("Pass")] * 19 + [row("Fail", critical=1)], 90)
		self.assertEqual((s.status, s.severity, s.score), ("Rejected", "Critical", 95.0))

	def test_open_noncritical_fail_is_medium(self):
		s = summarize([row("Pass")] * 19 + [row("Fail")], 90)
		self.assertEqual((s.status, s.severity), ("Rejected", "Medium"))

	def test_corrected_on_spot_accepted_when_score_ok(self):
		s = summarize([row("Pass")] * 19 + [row("Fail", critical=1, corrected=1)], 90)
		self.assertEqual((s.status, s.open_findings, s.corrected_on_spot_count), ("Accepted", 0, 1))

	def test_corrected_but_below_passing_is_low(self):
		s = summarize([row("Pass")] * 7 + [row("Fail", corrected=1)] * 3, 90)
		self.assertEqual((s.status, s.severity, s.score), ("Rejected", "Low", 70.0))

	def test_next_due(self):
		self.assertEqual(str(next_due("2026-09-30", "Weekly")), "2026-10-07")
		self.assertEqual(str(next_due("2026-09-30", "Monthly")), "2026-10-30")
		self.assertEqual(str(next_due("2026-09-30", "Quarterly")), "2026-12-30")

	def test_schedule_status(self):
		self.assertEqual(schedule_status_for("2026-09-29", "2026-09-30"), "Overdue")
		self.assertEqual(schedule_status_for("2026-09-30", "2026-09-30"), "Due")
		self.assertEqual(schedule_status_for("2026-10-01", "2026-09-30"), "Current")

	def test_as_needed_has_no_due_date(self):
		self.assertIsNone(next_due("2026-09-30", "As Needed"))
		self.assertEqual(schedule_status_for(None, periodicity="As Needed"), "Not Scheduled")

	def test_trip_status(self):
		self.assertEqual(trip_status("Pre-Departure", "Not Scheduled"), "Awaiting Return")
		self.assertEqual(trip_status("Post-Return", "Awaiting Return"), "Not Scheduled")
		self.assertEqual(trip_status("Routine", "Awaiting Return"), "Awaiting Return")
		self.assertEqual(trip_status("Routine", "Not Scheduled"), "Not Scheduled")


class IntegrationTestHousekeepingInspection(IntegrationTestCase):
	"""Add DB-backed tests here (requires Location, Quality Procedure and Employee fixtures)."""

	pass
