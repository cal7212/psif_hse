# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr, flt

REPAIR = "Repair"


class QCUnit(Document):
	def autoname(self):
		# New builds are named by TrulinX work order; repairs by RGA number.
		self.normalise_ids()
		if self.job_type == REPAIR:
			if not self.rga_number:
				frappe.throw(_("Enter the RGA Number for a repair."))
			rga = self.rga_number
			self.name = rga if rga.startswith("RGA") else f"RGA-{rga}"
		else:
			if not self.trulinx_work_order:
				frappe.throw(_("Enter the TrulinX Work Order for a new build."))
			self.name = self.trulinx_work_order

	def validate(self):
		self.normalise_ids()
		self.serial_no = cstr(self.serial_no).strip() or None
		self.validate_job_type_change()
		self.validate_unique_serial()
		self.set_test_pressures()
		self.validate_hoses()
		self.validate_status_change()

	def normalise_ids(self):
		self.trulinx_work_order = normalise_wo(self.trulinx_work_order) or None
		self.rga_number = normalise_wo(self.rga_number) or None

	def validate_job_type_change(self):
		if self.is_new() or not self.has_value_changed("job_type"):
			return
		if frappe.db.exists("QC Inspection", {"qc_unit": self.name, "docstatus": ["<", 2]}):
			frappe.throw(_("Job Type cannot change after inspections have been recorded."))

	def validate_unique_serial(self):
		if not self.serial_no:
			return
		other = frappe.db.get_value(
			"QC Unit", {"serial_no": self.serial_no, "name": ("!=", self.name)}, "name"
		)
		if other:
			frappe.throw(_("Serial No {0} is already used by QC Unit {1}").format(self.serial_no, other))

	def get_shop_defaults(self) -> frappe._dict:
		if not self.shop:
			return frappe._dict()
		return frappe._dict(
			frappe.db.get_value(
				"Build Shop", self.shop, ["test_pressure_multiplier", "default_hold_time_sec"], as_dict=True
			)
			or {}
		)

	def set_test_pressures(self):
		shop = self.get_shop_defaults()
		mult = flt(shop.test_pressure_multiplier)
		if mult and not flt(self.proof_test_psi) and flt(self.max_operating_psi):
			if self.product_type in ("Power Unit", "Manifold", "Valve Stand"):
				self.proof_test_psi = round(flt(self.max_operating_psi) * mult, 0)
		for h in self.hoses:
			if mult and not flt(h.test_pressure_psi) and flt(h.working_pressure_psi):
				h.test_pressure_psi = round(flt(h.working_pressure_psi) * mult, 0)
			if not cint(h.hold_time_sec) and cint(shop.default_hold_time_sec):
				h.hold_time_sec = cint(shop.default_hold_time_sec)

	def validate_hoses(self):
		self.hose_count = len(self.hoses)
		if self.hoses and self.product_type != "Hose Assembly":
			frappe.throw(_("Hose rows are only used when Product Type is Hose Assembly."))
		seen = set()
		for h in self.hoses:
			h.hose_tag = cstr(h.hose_tag).strip().upper()
			if h.hose_tag in seen:
				frappe.throw(_("Row {0}: Hose Tag {1} is listed twice.").format(h.idx, h.hose_tag))
			seen.add(h.hose_tag)
			if flt(h.crimp_tolerance) < 0:
				frappe.throw(_("Row {0}: Crimp tolerance must be positive.").format(h.idx))
		if seen:
			other = frappe.get_all(
				"QC Hose Assembly",
				filters={
					"parenttype": "QC Unit",
					"hose_tag": ["in", list(seen)],
					"parent": ["!=", self.name],
				},
				fields=["hose_tag", "parent"],
				limit=1,
			)
			if other:
				frappe.throw(
					_("Hose Tag {0} is already used on {1}.").format(other[0].hose_tag, other[0].parent)
				)

	def validate_status_change(self):
		if self.status in ("Released", "Shipped") and (self.open_non_conformances or 0) > 0:
			frappe.throw(_("Cannot release a unit with open Non Conformances."))


def normalise_wo(value) -> str:
	"""TrulinX WO and RGA numbers are matched as text: trim, upper-case, drop inner spaces.
	Adjust here if TrulinX pads with leading zeros (e.g. keep or strip them consistently)."""
	return cstr(value).strip().upper().replace(" ", "")
