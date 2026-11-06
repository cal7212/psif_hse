# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from hse.hse import snapshot as sn

ET = ZoneInfo("America/New_York")
USER = "_t_snapshot@example.com"


class UnitTestSnapshotPeriods(UnitTestCase):
	def test_weekly_is_prior_monday_to_sunday(self):
		for on in (date(2026, 11, 2), date(2026, 11, 4), date(2026, 11, 8)):
			self.assertEqual(sn.period_for(sn.WEEKLY, on), (date(2026, 10, 26), date(2026, 11, 1)))

	def test_monthly_is_prior_calendar_month(self):
		self.assertEqual(
			sn.period_for(sn.MONTHLY, date(2026, 11, 2)), (date(2026, 10, 1), date(2026, 10, 31))
		)
		self.assertEqual(sn.period_for(sn.MONTHLY, date(2027, 1, 4)), (date(2026, 12, 1), date(2026, 12, 31)))

	def test_previous_period(self):
		self.assertEqual(
			sn.previous_period(sn.WEEKLY, date(2026, 10, 26)), (date(2026, 10, 19), date(2026, 10, 25))
		)
		self.assertEqual(
			sn.previous_period(sn.MONTHLY, date(2026, 10, 1)), (date(2026, 9, 1), date(2026, 9, 30))
		)

	def test_first_monday(self):
		self.assertTrue(sn.is_first_monday(date(2026, 11, 2)))
		self.assertFalse(sn.is_first_monday(date(2026, 11, 9)))
		self.assertFalse(sn.is_first_monday(date(2026, 11, 3)))

	def test_change_text(self):
		self.assertEqual(sn.change_text(33.3, 50.0, "Percent"), "-16.7 pts")
		self.assertEqual(sn.change_text(3, 1, "Nos"), "+2")
		self.assertIsNone(sn.change_text(None, 1, "Nos"))
		self.assertEqual(sn.fmt(None, "Nos"), sn.DASH)

	def test_now_label_once(self):
		self.assertEqual(sn.now_label("Assets Out of Service (now)", True), "Assets Out of Service (now)")
		self.assertEqual(sn.now_label("Assets Out of Service", True), "Assets Out of Service (now)")
		self.assertEqual(sn.now_label("Rework records opened", False), "Rework records opened")


class TestSnapshot(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("User", USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": USER,
					"first_name": "Snapshot",
					"user_type": "System User",
					"send_welcome_email": 0,
					"roles": [{"role": "System Manager"}],
				}
			).insert(ignore_permissions=True)
		frappe.db.delete(sn.SNAPSHOT)
		doc = frappe.get_single(sn.SETTINGS)
		doc.weekly_enabled = 1
		doc.monthly_enabled = 1
		doc.attach_pdf = 0
		doc.time_zone = "America/New_York"
		doc.send_hour = 8
		doc.set("recipients", [])
		doc.append(
			"recipients", {"email": "totals@example.com", "version": "Totals", "weekly": 1, "monthly": 1}
		)
		doc.append("recipients", {"user": USER, "version": "Internal", "weekly": 1, "monthly": 0})
		doc.save(ignore_permissions=True)

	def test_internal_needs_system_user(self):
		doc = frappe.get_single(sn.SETTINGS)
		doc.append("recipients", {"email": "outside@example.com", "version": "Internal"})
		self.assertRaises(frappe.ValidationError, doc.save, ignore_permissions=True)

	def test_recipients_by_frequency(self):
		self.assertEqual(sn.recipients(sn.WEEKLY), {"Totals": ["totals@example.com"], "Internal": [USER]})
		self.assertEqual(sn.recipients(sn.MONTHLY), {"Totals": ["totals@example.com"], "Internal": []})

	def test_due_window(self):
		doc = frappe.get_single(sn.SETTINGS)
		first_monday = datetime(2026, 11, 2, 8, 5, tzinfo=ET)
		self.assertEqual(sn.due(doc, first_monday), [sn.WEEKLY, sn.MONTHLY])
		self.assertEqual(sn.due(doc, first_monday.replace(hour=7)), [])
		self.assertEqual(sn.due(doc, datetime(2026, 11, 9, 9, 0, tzinfo=ET)), [sn.WEEKLY])
		self.assertEqual(sn.due(doc, datetime(2026, 11, 3, 9, 0, tzinfo=ET)), [])
		doc.weekly_enabled = 0
		self.assertEqual(sn.due(doc, datetime(2026, 11, 9, 9, 0, tzinfo=ET)), [])

	def test_build_render_and_store(self):
		data = sn.build(sn.WEEKLY, date(2026, 11, 2), "America/New_York")
		self.assertEqual([g["group"] for g in data["scorecard"]], ["Safety", "Training", "Quality"])
		self.assertEqual(len(data["pillars"]), 3)
		totals = sn.render(data, sn.TOTALS)
		internal = sn.render(data, sn.INTERNAL)
		self.assertIn("Weekly Safety, Training and Quality Snapshot", totals)
		self.assertNotIn("Records <span", totals)
		self.assertIn("Records <span", internal)
		self.assertIn("first snapshot", totals)
		self.assertNotIn("(now) (now)", totals)

		name = sn.send(sn.WEEKLY, date(2026, 11, 2))
		snap = frappe.get_doc(sn.SNAPSHOT, name)
		self.assertEqual(snap.status, "Sent")
		self.assertEqual(str(snap.period_start), "2026-10-26")
		self.assertIn("recordable_cases", json.loads(snap.values_json))
		self.assertTrue(sn.already_sent(sn.WEEKLY, date(2026, 10, 26)))
		doc = frappe.get_single(sn.SETTINGS)
		self.assertEqual(sn.due(doc, datetime(2026, 11, 2, 8, 30, tzinfo=ET)), [sn.MONTHLY])

		# The next week's "(now)" rows compare with the stored snapshot.
		later = sn.build(sn.WEEKLY, date(2026, 11, 9), "America/New_York")
		self.assertNotIn("first snapshot", sn.render(later, sn.TOTALS))

	def test_monthly_has_reviews_section_key(self):
		data = sn.build(sn.MONTHLY, date(2026, 11, 2), "America/New_York")
		self.assertIn("October 2026", data["period"])
		self.assertEqual(data["prev_label"], "September")
		self.assertIsInstance(data["reviews"], list)

	def test_only_system_manager(self):
		frappe.set_user("Guest")
		try:
			self.assertRaises(frappe.PermissionError, sn.preview, "Weekly", "Totals")
		finally:
			frappe.set_user("Administrator")
