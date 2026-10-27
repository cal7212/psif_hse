# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""bench --site <test-site> run-tests --module hse.shop_qc.test_missing_parts_layout"""

import json
from pathlib import Path

from frappe.tests import UnitTestCase

DOCTYPES = Path(__file__).parent / "doctype"


class UnitTestMissingPartsLayout(UnitTestCase):
	def test_missing_parts_shown_for_every_product_type(self):
		"""Missing parts apply to any build, not only Power Units."""
		for name in ("qc_unit", "qc_inspection"):
			meta = json.loads((DOCTYPES / name / f"{name}.json").read_text())
			section = next(f for f in meta["fields"] if f["fieldname"] == "section_missing_parts")
			self.assertFalse(section.get("depends_on"), name)
			table = next(f for f in meta["fields"] if f["fieldname"] == "missing_parts")
			self.assertFalse(table.get("depends_on") or table.get("hidden"), name)
