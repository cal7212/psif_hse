# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import UnitTestCase

from hse.hse.osha_recordkeeping import incidence_rate, summarize


def case(outcome, away=0, restricted=0, key="injury"):
	return frappe._dict(outcome=outcome, days_away=away, days_restricted=restricted, illness_key=key)


class UnitTestOSHA300ASummary(UnitTestCase):
	def test_summarize(self):
		t = summarize([case("days_away", 5), case("transfer", 0, 3), case("other", key=None)])
		self.assertEqual((t.total_days_away_cases, t.total_transfer_cases, t.total_other_cases), (1, 1, 1))
		self.assertEqual((t.total_days_away, t.total_transfer_days), (5, 3))
		self.assertEqual((t.total_injury, t.cases_missing_type), (2, 1))

	def test_incidence_rate(self):
		self.assertEqual(incidence_rate(3, 100000), 6.0)
		self.assertEqual(incidence_rate(1, 0), 0.0)
