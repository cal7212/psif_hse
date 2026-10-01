# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr


class HPUUnit(Document):
	def autoname(self):
		# Normalise before the name is taken from trulinx_work_order.
		self.trulinx_work_order = normalise_wo(self.trulinx_work_order)

	def validate(self):
		self.trulinx_work_order = normalise_wo(self.trulinx_work_order)
		self.serial_no = cstr(self.serial_no).strip() or None
		self.validate_unique_serial()
		self.validate_status_change()

	def validate_unique_serial(self):
		if not self.serial_no:
			return
		other = frappe.db.get_value(
			"HPU Unit", {"serial_no": self.serial_no, "name": ("!=", self.name)}, "name"
		)
		if other:
			frappe.throw(
				_("Serial No {0} is already used by HPU Unit {1}").format(self.serial_no, other)
			)

	def validate_status_change(self):
		# QC status is driven by HPU Build Inspection / Non Conformance (next phase).
		# Until then, block manual release while Non Conformances are open.
		if self.status in ("Released", "Shipped") and (self.open_non_conformances or 0) > 0:
			frappe.throw(_("Cannot release an HPU with open Non Conformances."))


def normalise_wo(value) -> str:
	"""TrulinX WO numbers are matched as text: trim, upper-case, drop inner spaces.
	Adjust here if TrulinX pads with leading zeros (e.g. keep or strip them consistently)."""
	return cstr(value).strip().upper().replace(" ", "")
