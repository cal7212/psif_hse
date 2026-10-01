# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.tests import UnitTestCase
from frappe.utils import getdate

from hse.hse.doctype.sds.sds import summarize_use


class UnitTestSDS(UnitTestCase):
	def test_no_locations(self):
		self.assertEqual(summarize_use([]), (0, None, None, None))

	def test_still_in_use(self):
		rows = [{"start_date": "2026-01-01"}, {"start_date": "2025-06-01", "end_date": "2025-12-31"}]
		self.assertEqual(summarize_use(rows), (1, getdate("2025-06-01"), None, None))

	def test_out_of_use_sets_30_year_retention(self):
		rows = [
			{"start_date": "2020-01-01", "end_date": "2024-03-15"},
			{"start_date": "2021-01-01", "end_date": "2025-07-01"},
		]
		in_use, first, last, keep = summarize_use(rows)
		self.assertEqual((in_use, first, last), (0, getdate("2020-01-01"), getdate("2025-07-01")))
		self.assertEqual(keep, getdate("2055-07-01"))
