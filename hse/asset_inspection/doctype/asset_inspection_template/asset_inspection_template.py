# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class AssetInspectionTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hse.asset_inspection.doctype.asset_inspection_template_item.asset_inspection_template_item import (
			AssetInspectionTemplateItem,
		)

		asset_category: DF.Link | None
		disabled: DF.Check
		frequency_note: DF.Data | None
		instructions: DF.TextEditor | None
		items: DF.Table[AssetInspectionTemplateItem]
		quality_procedure: DF.Link | None
		template_name: DF.Data | None
	# end: auto-generated types

	def validate(self):
		if not self.items:
			frappe.throw(_("Add at least one checklist item."))
		seen = set()
		for row in self.items:
			key = (row.check_item or "").strip().lower()
			if key in seen:
				frappe.throw(_("Row {0}: duplicate check item '{1}'.").format(row.idx, row.check_item))
			seen.add(key)
			if row.numeric and row.min_value and row.max_value and row.min_value > row.max_value:
				frappe.throw(_("Row {0}: Min Value cannot exceed Max Value.").format(row.idx))
			if not row.numeric:
				row.min_value = row.max_value = 0
				row.uom = None
