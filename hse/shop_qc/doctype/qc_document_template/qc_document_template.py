# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr


class QCDocumentTemplate(Document):
	def validate(self):
		seen = set()
		for row in self.documents:
			row.document = cstr(row.document).strip()
			key = row.document.lower()
			if key in seen:
				frappe.throw(_("Row {0}: {1} is listed more than once.").format(row.idx, row.document))
			seen.add(key)
		if self.disabled:
			self.is_default = 0

	def on_update(self):
		if not self.is_default:
			return
		# One default per category and product type
		others = frappe.get_all(
			"QC Document Template",
			filters={
				"category": self.category,
				"product_type": self.product_type or ("is", "not set"),
				"is_default": 1,
				"name": ("!=", self.name),
			},
			pluck="name",
		)
		for name in others:
			frappe.db.set_value("QC Document Template", name, "is_default", 0)
