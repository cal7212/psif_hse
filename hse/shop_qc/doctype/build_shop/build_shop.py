# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class BuildShop(Document):
	def validate(self):
		self.inspection_prefix = (self.inspection_prefix or "").strip().upper()
		if not re.fullmatch(r"[A-Z0-9]{2,6}", self.inspection_prefix):
			frappe.throw(_("Inspection Number Prefix must be 2-6 letters or digits, e.g. HBI."))
		other = frappe.db.get_value(
			"Build Shop", {"inspection_prefix": self.inspection_prefix, "name": ("!=", self.name)}, "name"
		)
		if other:
			frappe.throw(_("Prefix {0} is already used by {1}.").format(self.inspection_prefix, other))
		if self.test_pressure_multiplier and flt(self.test_pressure_multiplier) < 1:
			frappe.throw(_("Test Pressure Multiplier should be 1 or more."))
