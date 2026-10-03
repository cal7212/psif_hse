# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class QCInspectionTemplate(Document):
	def validate(self):
		self.model_prefix = (self.model_prefix or "").strip().upper() or None
		self.product_type = self.product_type or None
		if not self.quality_procedure and self.stage:
			shop = frappe.db.get_value("QC Stage", self.stage, "shop")
			if shop:
				self.quality_procedure = frappe.db.get_value("Build Shop", shop, "quality_procedure")
		for row in self.items:
			if not row.numeric:
				row.unit_spec_field = None
				row.min_value = row.max_value = 0
			if row.unit_spec_field:
				row.min_value = row.max_value = 0
				if flt(row.tolerance_minus_pct) < 0 or flt(row.tolerance_plus_pct) < 0:
					frappe.throw(_("Row {0}: tolerances must be positive percentages.").format(row.idx))
			if row.min_value and row.max_value and flt(row.min_value) > flt(row.max_value):
				frappe.throw(_("Row {0}: Min Value is greater than Max Value.").format(row.idx))
