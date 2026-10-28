# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import now_datetime

from hse.housekeeping_inspection.doctype.housekeeping_inspection.housekeeping_inspection import summarize
from hse.housekeeping_inspection.utils import next_due, schedule_status_for, trip_status
from hse.testing_fixtures import ensure_company, ensure_gender

PROC = "_Test Housekeeping Procedure"
TEMPLATE = "_Test Housekeeping Template"
AREA = "_Test Housekeeping Area"


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


class IntegrationTestHousekeepingRework(IntegrationTestCase):
	"""A rejected housekeeping inspection raises a Rework; escalation keeps the links."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Quality Procedure", PROC):
			frappe.get_doc({"doctype": "Quality Procedure", "quality_procedure_name": PROC}).insert()
		if not frappe.db.exists("Housekeeping Inspection Template", TEMPLATE):
			frappe.get_doc(
				{
					"doctype": "Housekeeping Inspection Template",
					"template_name": TEMPLATE,
					"quality_procedure": PROC,
					"require_photo_on_fail": 0,
					"items": [
						{"check_item": "Aisles clear"},
						{"check_item": "Exits unobstructed", "is_critical": 1},
					],
				}
			).insert()
		company = ensure_company()
		if not frappe.db.exists("Housekeeping Area", AREA):
			frappe.get_doc(
				{
					"doctype": "Housekeeping Area",
					"area_name": AREA,
					"company": company,
					"template": TEMPLATE,
					"periodicity": "Weekly",
				}
			).insert()
		cls.employee = frappe.db.get_value("Employee", {"status": "Active", "company": company}, "name")
		if not cls.employee:
			cls.employee = (
				frappe.get_doc(
					{
						"doctype": "Employee",
						"first_name": "_Test Housekeeping Inspector",
						"gender": ensure_gender(),
						"date_of_birth": "1990-01-01",
						"date_of_joining": "2020-01-01",
						"company": company,
					}
				)
				.insert()
				.name
			)

	def make_inspection(self, critical_result="Fail"):
		return frappe.get_doc(
			{
				"doctype": "Housekeeping Inspection",
				"housekeeping_area": AREA,
				"template": TEMPLATE,
				"inspection_reason": "Routine",
				"inspection_date": now_datetime(),
				"inspected_by": self.employee,
				"items": [
					{"check_item": "Aisles clear", "result": "Pass"},
					{
						"check_item": "Exits unobstructed",
						"is_critical": 1,
						"result": critical_result,
						"finding": "Pallet blocking the exit" if critical_result == "Fail" else None,
					},
				],
			}
		).insert()

	def test_rejected_inspection_raises_rework(self):
		insp = self.make_inspection()
		insp.submit()
		insp.reload()
		self.assertEqual(insp.status, "Rejected")
		self.assertTrue(insp.non_conformance.startswith("QA-RW-"))
		rw = frappe.get_doc("Nonconformance Report", insp.non_conformance)
		self.assertEqual(rw.record_type, "Rework")
		self.assertEqual(rw.severity, "Critical")
		self.assertEqual((rw.housekeeping_area, rw.housekeeping_inspection), (AREA, insp.name))
		self.assertIn("Pallet blocking the exit", rw.rw_requirement)

	def test_rework_resolution_gate_names_rework(self):
		insp = self.make_inspection()
		insp.submit()
		from hse.quality_metrics.rework import EVAL, NO

		rw = frappe.get_doc("Nonconformance Report", insp.reload().non_conformance)
		for field in EVAL:
			rw.set(field, NO)
		rw.status = "Resolved"
		with self.assertRaisesRegex(frappe.ValidationError, "Cannot resolve this Rework"):
			rw.save()

	def test_escalated_rework_keeps_housekeeping_links(self):
		from hse.quality_metrics.rework import escalate_to_ncr

		insp = self.make_inspection()
		insp.submit()
		rw_name = insp.reload().non_conformance
		ncr = escalate_to_ncr(rw_name, ["crit_supplier"], "Escalation test")
		self.assertTrue(ncr.startswith("QA-NC-"))
		self.assertEqual(insp.reload().non_conformance, ncr)
		nc = frappe.get_doc("Nonconformance Report", ncr)
		self.assertEqual((nc.housekeeping_area, nc.housekeeping_inspection), (AREA, insp.name))
