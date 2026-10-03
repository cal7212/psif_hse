# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, cint, cstr, getdate


class MeasuringInstrument(Document):
	def before_naming(self):
		self.instrument_id = cstr(self.instrument_id).strip().upper()

	def validate(self):
		self.instrument_id = cstr(self.instrument_id).strip().upper()
		if not cint(self.calibration_required):
			return
		if self.last_calibrated and cint(self.calibration_interval_months) > 0:
			self.calibration_due = add_months(self.last_calibrated, cint(self.calibration_interval_months))
		if (
			self.last_calibrated
			and self.calibration_due
			and getdate(self.calibration_due) < getdate(self.last_calibrated)
		):
			frappe.throw(_("Calibration Due cannot be before Last Calibrated."))
