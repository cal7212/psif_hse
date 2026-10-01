# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class HousekeepingInspectionTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hse.housekeeping_inspection.doctype.housekeeping_inspection_template_item.housekeeping_inspection_template_item import (
			HousekeepingInspectionTemplateItem,
		)

		disabled: DF.Check
		instructions: DF.TextEditor | None
		items: DF.Table[HousekeepingInspectionTemplateItem]
		passing_score: DF.Percent
		quality_procedure: DF.Link
		require_photo_on_fail: DF.Check
		template_name: DF.Data
	# end: auto-generated types

	def validate(self):
		if not self.items:
			frappe.throw(_("Add at least one checklist item."))
		if not 0 <= flt(self.passing_score) <= 100:
			frappe.throw(_("Passing Score must be between 0 and 100."))
		seen = set()
		for row in self.items:
			key = (row.check_item or "").strip().lower()
			if key in seen:
				frappe.throw(_("Row {0}: duplicate check item '{1}'.").format(row.idx, row.check_item))
			seen.add(key)
