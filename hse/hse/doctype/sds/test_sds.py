# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import getdate

from hse.hse.doctype.sds.sds import summarize_use
from hse.hse.sds_label import get_ghs_label_data


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


class IntegrationTestGHSLabel(IntegrationTestCase):
	def make_sds(self, **kw):
		values = {
			"doctype": "SDS",
			"product_name": "_T Label Solvent",
			"signal_word": "Danger",
			"pictograms": [{"pictogram": "Flame"}, {"pictogram": "Exclamation Mark"}],
			"hazard_statements": "H225 Highly flammable liquid and vapor.\nH319 Causes serious eye irritation.",
			"precautionary_statements": "P210 Keep away from heat.\nP280 Wear eye protection.",
			"manufacturer_name": "_T Chemical Co.",
			"adress_one": "1 Test Way",
			"manufacturer_city": "Palm Bay",
			"man_phone": "321-555-0100",
		}
		values.update(kw)
		return frappe.get_doc(values).insert(ignore_permissions=True)

	def test_complete_label(self):
		sds = self.make_sds()
		g = get_ghs_label_data(sds.name)
		self.assertEqual(g.missing, [])
		self.assertEqual([p.code for p in g.pictograms], ["GHS02", "GHS07"])
		self.assertTrue(g.pictograms[0].src.startswith("data:image/png;base64,"))
		self.assertEqual(g.hazards[1], "H319 Causes serious eye irritation.")
		html = frappe.get_print("SDS", sds.name, print_format="GHS Label 2x4", no_letterhead=1)
		self.assertIn("DANGER", html)
		self.assertIn("P280 Wear eye protection.", html)
		self.assertNotIn("GHS label not printed", html)

	def test_missing_elements_block_label(self):
		sds = self.make_sds(precautionary_statements=None, adress_one=None, manufacturer_city=None)
		g = get_ghs_label_data(sds.name)
		self.assertEqual(len(g.missing), 2)
		html = frappe.get_print("SDS", sds.name, print_format="GHS Label 2x4", no_letterhead=1)
		self.assertIn("GHS label not printed", html)

	def test_non_hazardous_product(self):
		sds = self.make_sds(
			signal_word="No Signal Word", pictograms=[], hazard_statements=None, precautionary_statements=None
		)
		g = get_ghs_label_data(sds.name)
		self.assertEqual(g.missing, [])
		self.assertEqual(g.signal, "")
