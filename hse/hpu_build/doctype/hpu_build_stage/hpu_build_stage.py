# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class HPUBuildStage(Document):
	def validate(self):
		if self.is_final_release:
			other = frappe.db.get_value(
				"HPU Build Stage", {"is_final_release": 1, "disabled": 0, "name": ("!=", self.name)}, "name"
			)
			if other and not self.disabled:
				frappe.throw(_("{0} is already the Final Release stage.").format(frappe.bold(other)))
			self.is_required = 1
		if self.sequence is None or self.sequence < 0:
			frappe.throw(_("Sequence must be zero or greater."))
