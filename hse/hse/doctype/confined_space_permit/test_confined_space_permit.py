# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import add_to_date, now_datetime

from hse.hse.doctype.confined_space_permit.confined_space_permit import issue_errors, judge_reading
from hse.hse.page.hse_dashboard.hse_dashboard import att_csp_expired
from hse.hse.permits import close_permit
from hse.testing_fixtures import ensure_company, ensure_employee

CSP = "Confined Space Permit"
LIMITS = frappe._dict(oxygen_min=19.5, oxygen_max=23.5, lel_max=10, h2s_max=10, co_max=35)


class UnitTestConfinedSpacePermit(UnitTestCase):
	def test_reading_judged_against_limits(self):
		t = frappe._dict
		self.assertEqual(judge_reading(t(oxygen_pct=20.9, lel_pct=0), LIMITS), "Acceptable")
		self.assertEqual(judge_reading(t(oxygen_pct=19.0, lel_pct=0), LIMITS), "Not Acceptable")
		self.assertEqual(judge_reading(t(oxygen_pct=24.0, lel_pct=0), LIMITS), "Not Acceptable")
		self.assertEqual(judge_reading(t(oxygen_pct=20.9, lel_pct=12), LIMITS), "Not Acceptable")
		self.assertEqual(judge_reading(t(oxygen_pct=20.9, lel_pct=0, h2s_ppm=15), LIMITS), "Not Acceptable")
		self.assertEqual(judge_reading(t(oxygen_pct=20.9, lel_pct=0, co_ppm=40), LIMITS), "Not Acceptable")
		self.assertEqual(judge_reading(t(oxygen_pct=None, lel_pct=0), LIMITS), "")  # oxygen not taken yet
		self.assertEqual(judge_reading(t(oxygen_pct=0, lel_pct=0), LIMITS), "")  # empty Float saves as 0

	def test_entrant_cannot_also_attend(self):
		doc = frappe.new_doc(CSP)
		doc.update(
			{
				"workers": [
					{"worker_name": "Al Poe", "role": "Entrant"},
					{"worker_name": "al poe", "role": "Attendant"},
				]
			}
		)
		self.assertTrue(any("attendant stays outside" in e for e in issue_errors(doc)))


class IntegrationTestConfinedSpacePermit(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = ensure_company()
		cls.supervisor = ensure_employee("_Test Entry Supervisor", cls.company)

	def make(self, o2=20.9):
		start = now_datetime()
		return frappe.get_doc(
			{
				"doctype": CSP,
				"space_name": "_Test reservoir T-3",
				"company": self.company,
				"permit_start": start,
				"permit_end": add_to_date(start, hours=8),
				"entry_supervisor": self.supervisor,
				"purpose": "Clean reservoir",
				"hz_oxygen": 1,
				"iso_lockout": 1,
				"rescue_service": "Non-Entry Retrieval",
				"summon_rescue": "Attendant radios the supervisor and calls 911",
				"communication_method": "Voice",
				"workers": [
					{"worker_name": "_Test Entrant", "role": "Entrant"},
					{"worker_name": "_Test Attendant", "role": "Attendant"},
				],
				"atmospheric_tests": [
					{
						"test_type": "Pre-Entry",
						"oxygen_pct": o2,
						"lel_pct": 0,
						"tested_by": "TS",
						"test_time": start,
					}
				],
			}
		).insert()

	def test_bad_pre_entry_blocks_issue(self):
		doc = self.make(o2=18.0)
		self.assertEqual(doc.atmospheric_tests[0].result, "Not Acceptable")
		self.assertRaises(frappe.ValidationError, doc.submit)

	def test_issue_test_and_close(self):
		doc = self.make()
		doc.submit()
		self.assertEqual((doc.status, doc.issued_by), ("Issued", frappe.session.user))
		doc.append(
			"atmospheric_tests",
			{
				"test_type": "Periodic",
				"oxygen_pct": 20.8,
				"lel_pct": 1,
				"tested_by": "TS",
				"test_time": now_datetime(),
			},
		)
		doc.workers[0].time_in = now_datetime()
		doc.save()
		self.assertEqual(doc.atmospheric_tests[1].result, "Acceptable")
		self.assertRaises(
			frappe.ValidationError, close_permit, CSP, doc.name, "Prohibited Condition"
		)  # needs notes
		close_permit(CSP, doc.name, "Work Completed")
		doc.reload()
		self.assertEqual((doc.status, doc.closure_reason), ("Closed", "Work Completed"))
		self.assertTrue(doc.workers[0].time_out)

	def test_expired_permit_on_dashboard(self):
		doc = self.make()
		doc.submit()
		doc.db_set("permit_end", add_to_date(now_datetime(), minutes=-5))
		self.assertTrue(att_csp_expired())
