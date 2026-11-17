# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""bench --site <test-site> run-tests --module hse.shop_qc.test_rfd_layout"""

import json
import re
from pathlib import Path

from frappe.tests import UnitTestCase

HERE = Path(__file__).parent
UNIT = json.loads((HERE / "doctype" / "qc_unit" / "qc_unit.json").read_text())
PRINT = json.loads(
	(HERE / "print_format" / "qm_144_request_for_deviation" / "qm_144_request_for_deviation.json").read_text()
)


class UnitTestRFDLayout(UnitTestCase):
	def test_tab_sits_before_qc_status(self):
		order = UNIT["field_order"]
		self.assertLess(order.index("tab_rfd"), order.index("tab_qc"))
		self.assertEqual(order, [f["fieldname"] for f in UNIT["fields"]])

	def test_print_format_uses_existing_fields(self):
		"""Every doc.<field> in the QM-144 print is a QC Unit field."""
		fields = {f["fieldname"] for f in UNIT["fields"]} | {"name"}
		used = set(re.findall(r"doc\.(\w+)", PRINT["html"]))
		self.assertFalse(used - fields, used - fields)

	def test_change_order_sources_match(self):
		"""The RFD's Requested By must be a valid change order Source."""
		co = json.loads((HERE / "doctype" / "qc_change_order" / "qc_change_order.json").read_text())
		co_source = next(f for f in co["fields"] if f["fieldname"] == "source")["options"]
		rfd_source = next(f for f in UNIT["fields"] if f["fieldname"] == "rfd_source")["options"]
		self.assertEqual(set(rfd_source.split("\n")), set(co_source.split("\n")))
