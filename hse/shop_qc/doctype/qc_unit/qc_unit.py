# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr, flt

REPAIR = "Repair"
MAX_PMG = 10
PUMP_TYPES = ("Gear", "Vane", "Fixed Piston", "Variable Piston", "Screw", "Other")
SYSTEM_TYPES = ("Power Unit", "Manifold", "Valve Stand")
# PSIF System Construction Test Record: construction documentation and quality documents.
CONSTRUCTION_DOCUMENTS = (
	"Hydraulic Schematic",
	"Electrical Schematic",
	"Pneumatic Schematic",
	"Fabrication Drawing",
	"Mechanical Drawing",
	"Assembly Drawing",
	"General Arrangement",
	"Piping & Instrument Diagram",
	"Weld Specification",
	"Assembly Instructions",
	"Test Specification / F.A.T.",
	"Pipe Spool Drawing",
	"Bill of Materials",
	"Prior Project Photos",
	"Test Procedure",
	"Coating Specification",
	"Quality Specification",
	"Ship Loose Items List",
)
QUALITY_DOCUMENTS = (
	"Material Test Reports",
	"Safety Data Sheets",
	"Certificate of Conformance",
	"Calibration Certification",
	"Test Performance Records",
	"First Article Reports",
	"Dimensional Inspection",
	"Serial Number Records",
	"Test Procedure (F.A.T.)",
	"Standard Package - Data Sheets, Manual, Drawings",
)
REVIEW_AREAS = (
	"Design",
	"Documentation",
	"Layout",
	"Quality",
	"Logistics",
	"Scheduling",
	"Fabrication",
	"Plumbing",
	"Wiring",
	"Coatings",
	"Testing",
	"Non-Conformances",
	"Other",
)
CC_PER_GAL = 3785.41
IN3_PER_GAL = 231.0


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
		self.validate_pump_motor_groups()
		self.validate_circuit_items()
		self.set_order_documents()
		self.set_post_shipment_review()
		self.validate_status_change()

	def set_order_documents(self):
		if self.product_type not in SYSTEM_TYPES:
			return
		for table, names in (
			("construction_documents", CONSTRUCTION_DOCUMENTS),
			("quality_documents", QUALITY_DOCUMENTS),
		):
			if not self.get(table):
				for name in names:
					self.append(table, {"document": name})

	def set_post_shipment_review(self):
		if self.status == "Shipped" and not self.post_shipment_reviews:
			for area in REVIEW_AREAS:
				self.append("post_shipment_reviews", {"area": area})

	def validate_circuit_items(self):
		tags = {r.pmg_tag for r in self.pump_motor_groups}
		for table in ("circuit_devices", "accumulators"):
			for r in self.get(table):
				r.pmg_tag = cstr(r.pmg_tag).strip().upper() or None
				if r.pmg_tag and r.pmg_tag not in tags:
					frappe.throw(
						_("{0} row {1}: circuit {2} is not one of this unit's pump / motor groups.").format(
							_(self.meta.get_label(table)), r.idx, r.pmg_tag
						)
					)
		for r in self.accumulators:
			if flt(r.precharge_psi) < 0 or flt(r.volume_gal) < 0:
				frappe.throw(_("Accumulators row {0}: values cannot be negative.").format(r.idx))
		for r in self.proof_test_items:
			if flt(r.p1_psi) < 0 or flt(r.p2_psi) < 0:
				frappe.throw(_("Proof Test Items row {0}: pressures cannot be negative.").format(r.idx))

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

	def validate_pump_motor_groups(self):
		# The TrulinX sync sends one motor HP / pump type per work order: keep it in PMG-1.
		if self.product_type == "Power Unit" and (flt(self.motor_hp) or self.pump_type):
			if not self.pump_motor_groups:
				self.append("pump_motor_groups", {})
			first = self.pump_motor_groups[0]
			first.motor_hp = first.motor_hp or self.motor_hp
			if self.pump_type and not first.pump_type:
				if self.pump_type in PUMP_TYPES:
					first.pump_type = self.pump_type
				elif self.pump_type not in cstr(first.notes):
					note = _("Pump type: {0}").format(self.pump_type)
					first.notes = f"{first.notes}\n{note}" if first.notes else note

		self.pmg_count = len(self.pump_motor_groups)
		if self.pump_motor_groups and self.product_type != "Power Unit":
			frappe.throw(_("Pump / motor groups are only used when Product Type is Power Unit."))
		if self.pmg_count > MAX_PMG:
			frappe.throw(_("A power unit can have at most {0} pump / motor groups.").format(MAX_PMG))

		used = {cstr(r.pmg_tag).strip().upper() for r in self.pump_motor_groups if cstr(r.pmg_tag).strip()}
		seen = set()
		for r in self.pump_motor_groups:
			tag = cstr(r.pmg_tag).strip().upper()
			if not tag:
				n = r.idx
				while f"PMG-{n}" in used:
					n += 1
				tag = f"PMG-{n}"
				used.add(tag)
			if tag in seen:
				frappe.throw(_("PMG tag {0} is used more than once.").format(tag))
			seen.add(tag)
			r.pmg_tag = tag
			r.motor_voltage = r.motor_voltage or self.voltage
			r.motor_phase = r.motor_phase or self.phase
			r.motor_hz = r.motor_hz or self.hz
			if not flt(r.design_flow_gpm):
				r.design_flow_gpm = theoretical_flow(r)
			for field in ("relief_setting_psi", "compensator_setting_psi", "motor_hp", "motor_fla"):
				if flt(r.get(field)) < 0:
					frappe.throw(_("{0}: {1} cannot be negative.").format(tag, r.meta.get_label(field)))
			if flt(r.compensator_setting_psi) and flt(r.relief_setting_psi):
				if flt(r.compensator_setting_psi) >= flt(r.relief_setting_psi):
					frappe.msgprint(
						_(
							"{0}: compensator setting ({1} psi) is at or above the relief setting ({2} psi). "
							"Check the design values."
						).format(tag, r.compensator_setting_psi, r.relief_setting_psi),
						indicator="orange",
						alert=True,
					)

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


def theoretical_flow(r) -> float:
	"""Displacement x rated RPM, in GPM. 0 when either is missing."""
	per_gal = {"cc/rev": CC_PER_GAL, "in³/rev": IN3_PER_GAL}.get(r.displacement_uom)
	if not per_gal or not flt(r.displacement) or not flt(r.motor_rpm):
		return 0
	return flt(flt(r.displacement) * flt(r.motor_rpm) / per_gal, 2)


def normalise_wo(value) -> str:
	"""TrulinX WO and RGA numbers are matched as text: trim, upper-case, drop inner spaces.
	Adjust here if TrulinX pads with leading zeros (e.g. keep or strip them consistently)."""
	return cstr(value).strip().upper().replace(" ", "")
