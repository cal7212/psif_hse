# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import json
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase

from hse.shop_qc.install import DEFAULT_STAGES, create_sample_templates


class TestSampleTemplates(IntegrationTestCase):
	def test_every_sample_template_loads(self):
		data = json.loads((Path(__file__).parent / "sample_templates.json").read_text())
		stages = {name for rows in DEFAULT_STAGES.values() for name, *_ in rows}
		self.assertTrue({t["stage"] for t in data} <= stages, "sample template points at an unknown stage")
		create_sample_templates()
		for t in data:
			self.assertTrue(
				frappe.db.exists("QC Inspection Template", t["template_name"]), t["template_name"]
			)

	def test_light_assembly_seeded(self):
		self.assertEqual(frappe.db.get_value("Build Shop", "Light Assembly", "inspection_prefix"), "LAI")
		self.assertFalse(frappe.db.exists("Build Shop", "Small Assembly"))
