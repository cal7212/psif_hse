# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cstr, escape_html, flt, getdate

from hse.hpu_build.utils import (
	LOCKED_STATUSES,
	count_open_ncs,
	get_accepted_by_stage,
	get_stages,
	update_hpu_unit_status,
)

PASS, FAIL, NA = "Pass", "Fail", "N/A"
TEMPLATE_ROW_FIELDS = (
	"check_item", "criteria", "is_critical", "requires_photo", "numeric", "record_text",
	"min_value", "max_value", "uom", "unit_spec_field",
)
SPEC_LABELS = {
	"relief_setting_psi": "Relief Setting (psi)",
	"max_operating_psi": "Max Operating Pressure (psi)",
	"flow_gpm": "Design Flow (GPM)",
	"motor_hp": "Motor HP",
	"reservoir_gal": "Reservoir (gal)",
}


def evaluate_numeric(reading_value, min_value=None, max_value=None):
	"""Pass/Fail against optional limits. A limit of 0/None is 'not set'."""
	value = flt(reading_value)
	if min_value and value < flt(min_value):
		return FAIL
	if max_value and value > flt(max_value):
		return FAIL
	return PASS


class HPUBuildInspection(Document):
	# ------------------------------------------------------------------ validate
	def validate(self):
		self.validate_unit()
		self.validate_template()
		self.validate_reinspection()
		if not self.items:
			self.set_items_from_template()
		self.evaluate_numeric_readings()
		if self.docstatus == 0:
			self.status = "Pending"

	def validate_unit(self):
		status = frappe.db.get_value("HPU Unit", self.hpu_unit, "status")
		if status in LOCKED_STATUSES:
			frappe.throw(_("HPU Unit {0} is {1}; no further build inspections can be recorded.").format(
				frappe.bold(self.hpu_unit), status))
		if frappe.db.get_value("HPU Build Stage", self.stage, "disabled"):
			frappe.throw(_("Build Stage {0} is disabled.").format(frappe.bold(self.stage)))

	def validate_template(self):
		t = frappe.get_cached_doc("HPU Build Inspection Template", self.template)
		if t.disabled:
			frappe.throw(_("Inspection Template {0} is disabled.").format(frappe.bold(self.template)))
		if t.stage != self.stage:
			frappe.throw(_("Template {0} is for stage {1}, not {2}.").format(
				frappe.bold(self.template), frappe.bold(t.stage), frappe.bold(self.stage)))
		if t.model_prefix and not cstr(self.model).upper().startswith(t.model_prefix.upper()):
			frappe.throw(_("Template {0} applies to models starting with {1}; this unit is {2}.").format(
				frappe.bold(self.template), frappe.bold(t.model_prefix), frappe.bold(self.model)))
		if not self.quality_procedure:
			self.quality_procedure = t.quality_procedure

	def validate_reinspection(self):
		if not self.is_reinspection:
			self.reinspection_of = None
			return
		if not self.reinspection_of:
			frappe.throw(_("Select the original inspection in Re-inspection Of."))
		if self.reinspection_of == self.name:
			frappe.throw(_("An inspection cannot be a re-inspection of itself."))
		orig = frappe.db.get_value(
			"HPU Build Inspection", self.reinspection_of, ["hpu_unit", "stage", "status", "docstatus"], as_dict=True
		)
		if not orig or orig.docstatus != 1 or orig.status != "Rejected":
			frappe.throw(_("Re-inspection Of must be a submitted, Rejected inspection."))
		if orig.hpu_unit != self.hpu_unit or orig.stage != self.stage:
			frappe.throw(_("A re-inspection must be for the same HPU Unit ({0}) and stage ({1}).").format(
				frappe.bold(orig.hpu_unit), frappe.bold(orig.stage)))

	def set_items_from_template(self):
		self.set("items", [])
		for row in build_items(self.template, self.hpu_unit):
			self.append("items", row)

	def evaluate_numeric_readings(self):
		# Float fields default to 0, so a 0 reading is treated as "not entered".
		# A genuine zero reading should be marked Fail by the inspector.
		for row in self.items:
			if row.numeric and row.result != NA and flt(row.reading_value) != 0:
				row.result = evaluate_numeric(row.reading_value, row.min_value, row.max_value)

	# ------------------------------------------------------------------ submit
	def before_submit(self):
		self.check_readings_complete()
		self.check_test_equipment()
		self.check_hold_points()
		self.check_not_already_accepted()
		self.status = "Rejected" if self.get_failed_rows() else "Accepted"
		if self.status == "Accepted" and self.is_final_release():
			self.check_release_allowed()

	def check_readings_complete(self):
		errors = []
		for row in self.items:
			label = row.check_item
			if not row.result:
				errors.append(_("Row {0}: Result is required for '{1}'.").format(row.idx, label))
				continue
			if row.result == FAIL and not cstr(row.finding).strip():
				errors.append(_("Row {0}: Finding is required for failed item '{1}'.").format(row.idx, label))
			if row.result == NA:
				continue
			if row.numeric and row.result == PASS and flt(row.reading_value) == 0:
				errors.append(_("Row {0}: Enter the reading for '{1}'.").format(row.idx, label))
			if row.numeric and row.unit_spec_field and not (row.min_value or row.max_value):
				errors.append(_("Row {0}: '{1}' takes its limits from {2}, which is blank on HPU Unit {3}. "
					"Enter the design value on the unit and reload the checklist.").format(
					row.idx, label, SPEC_LABELS.get(row.unit_spec_field, row.unit_spec_field), self.hpu_unit))
			if row.record_text and not cstr(row.text_value).strip():
				errors.append(_("Row {0}: Record the value for '{1}'.").format(row.idx, label))
			if row.requires_photo and not row.photo:
				errors.append(_("Row {0}: A photo is required for '{1}'.").format(row.idx, label))
		if errors:
			frappe.throw("<br>".join(errors), title=_("Inspection Incomplete"))

	def check_test_equipment(self):
		if not any(r.numeric and r.result != NA for r in self.items):
			return
		if not self.gauge_id:
			frappe.throw(_("Enter the Gauge / Test Instrument ID used for the numeric readings."))
		on = getdate(self.inspection_date)
		for field, due in (("gauge_id", self.gauge_cal_due), ("flowmeter_id", self.flowmeter_cal_due)):
			if self.get(field) and not due:
				frappe.throw(_("Enter the calibration due date for instrument {0}.").format(frappe.bold(self.get(field))))
			if self.get(field) and getdate(due) < on:
				frappe.throw(_("Instrument {0} was out of calibration on the inspection date (due {1}).").format(
					frappe.bold(self.get(field)), frappe.format(due, "Date")))

	def check_hold_points(self):
		stage = frappe.get_cached_doc("HPU Build Stage", self.stage)
		if not stage.hold_point:
			return
		accepted = get_accepted_by_stage(self.hpu_unit)
		missing = [
			s.name for s in get_stages(required_only=True)
			if s.sequence < stage.sequence and s.name not in accepted
		]
		if missing:
			frappe.throw(
				_("Hold point: these earlier stages must be Accepted first: {0}").format(", ".join(missing)),
				title=_("Hold Point"),
			)

	def check_not_already_accepted(self):
		existing = frappe.db.get_value(
			"HPU Build Inspection",
			{"hpu_unit": self.hpu_unit, "stage": self.stage, "docstatus": 1, "status": "Accepted", "name": ("!=", self.name)},
			"name",
		)
		if existing:
			frappe.throw(_("Stage {0} is already Accepted for this unit ({1}). Cancel that inspection first if it must be repeated.").format(
				frappe.bold(self.stage), frappe.get_desk_link("HPU Build Inspection", existing)))

	def check_release_allowed(self):
		open_ncs = count_open_ncs(self.hpu_unit)
		if open_ncs:
			frappe.throw(_("HPU Unit {0} has {1} open Non Conformance(s). Resolve them before final release.").format(
				frappe.bold(self.hpu_unit), open_ncs), title=_("Release Blocked"))

	def on_submit(self):
		if self.status == "Rejected":
			self.create_non_conformance()
		else:
			self.link_reinspection_to_original_nc()
		update_hpu_unit_status(self.hpu_unit)

	def before_cancel(self):
		if frappe.db.get_value("HPU Unit", self.hpu_unit, "status") == "Shipped":
			frappe.throw(_("HPU Unit {0} has shipped; its build inspections cannot be cancelled.").format(
				frappe.bold(self.hpu_unit)))
		if self.status == "Accepted":
			later = frappe.get_all(
				"HPU Build Inspection",
				filters={"hpu_unit": self.hpu_unit, "docstatus": 1, "status": "Accepted",
					"stage_sequence": (">", self.stage_sequence or 0)},
				pluck="name",
			)
			if later:
				frappe.throw(_("Later stages were accepted after this one ({0}). Cancel those first.").format(
					", ".join(later)))

	def on_cancel(self):
		# Must be set on the instance: lets the inspection be cancelled even though
		# its Non Conformance / re-inspection link back to it.
		self.ignore_linked_doctypes = ("Non Conformance", "HPU Build Inspection", "HPU Unit")
		self.db_set("status", "Pending")
		if self.non_conformance:
			nc = frappe.get_doc("Non Conformance", self.non_conformance)
			if nc.status == "Open":
				nc.status = "Cancelled"
				nc.flags.ignore_permissions = True
				nc.add_comment("Info", _("Cancelled because HPU Build Inspection {0} was cancelled.").format(self.name))
				nc.save()
		if self.is_reinspection and self.reinspection_of:
			orig_nc = frappe.db.get_value("HPU Build Inspection", self.reinspection_of, "non_conformance")
			if orig_nc and frappe.db.get_value("Non Conformance", orig_nc, "hpu_reinspection") == self.name:
				if frappe.db.get_value("Non Conformance", orig_nc, "status") == "Resolved":
					frappe.throw(_("Non Conformance {0} was resolved using this re-inspection. Reopen it before cancelling.").format(
						frappe.bold(orig_nc)))
				frappe.db.set_value("Non Conformance", orig_nc, "hpu_reinspection", None)
		update_hpu_unit_status(self.hpu_unit)

	# ------------------------------------------------------------------ helpers
	def is_final_release(self) -> bool:
		return bool(frappe.get_cached_value("HPU Build Stage", self.stage, "is_final_release"))

	def get_failed_rows(self):
		return [r for r in self.items if r.result == FAIL]

	def create_non_conformance(self):
		failed = self.get_failed_rows()
		critical = any(r.is_critical for r in failed)

		def reading(r):
			if r.numeric:
				return escape_html(cstr(r.reading_value)) + (
					f" ({cstr(r.min_value or '')}–{cstr(r.max_value or '')})" if (r.min_value or r.max_value) else "")
			return escape_html(cstr(r.text_value))

		rows = "".join(
			"<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td></tr>".format(
				escape_html(cstr(r.check_item)), _("Yes") if r.is_critical else _("No"), reading(r), escape_html(cstr(r.finding)))
			for r in failed
		)
		details = (
			f"<p>{_('HPU Unit (TrulinX WO)')}: <b>{escape_html(self.hpu_unit)}</b> – {escape_html(cstr(self.model))}"
			f" {_('S/N')} {escape_html(cstr(self.serial_no))}<br>"
			f"{_('Stage')}: <b>{escape_html(self.stage)}</b><br>"
			f"{_('Inspection')}: <b>{self.name}</b> – {self.inspection_date}<br>"
			f"{_('Inspected By')}: {escape_html(cstr(self.inspector_name or self.inspected_by))}</p>"
			f"<table class='table table-bordered'><thead><tr><th>{_('Check Item')}</th><th>{_('Critical')}</th>"
			f"<th>{_('Reading')}</th><th>{_('Finding')}</th></tr></thead><tbody>{rows}</tbody></table>"
		)
		if self.remarks:
			details += f"<p>{_('Remarks')}: {escape_html(self.remarks)}</p>"

		nc = frappe.get_doc({
			"doctype": "Non Conformance",
			"subject": f"HPU QC failure - {self.hpu_unit} {self.stage} ({self.name})",
			"procedure": self.quality_procedure,
			"status": "Open",
			"details": details,
			"hpu_unit": self.hpu_unit,
			"hpu_build_inspection": self.name,
			"severity": "Critical" if critical else "Medium",
			"interim_control": _("HPU on QC Hold; do not test under pressure or ship until resolved.") if critical
				else _("HPU on QC Hold pending corrective action."),
		})
		nc.flags.ignore_permissions = True
		nc.insert()
		self.db_set("non_conformance", nc.name)
		frappe.msgprint(
			_("Non Conformance {0} created and HPU {1} placed on QC Hold.").format(
				frappe.get_desk_link("Non Conformance", nc.name), self.hpu_unit),
			indicator="red", alert=True,
		)

	def link_reinspection_to_original_nc(self):
		if not (self.is_reinspection and self.reinspection_of):
			return
		orig_nc = frappe.db.get_value("HPU Build Inspection", self.reinspection_of, "non_conformance")
		if orig_nc:
			frappe.db.set_value("Non Conformance", orig_nc, "hpu_reinspection", self.name)
			frappe.msgprint(
				_("Re-inspection linked to {0}. Complete verification and resolve it to clear the QC Hold.").format(
					frappe.get_desk_link("Non Conformance", orig_nc)),
				indicator="green", alert=True,
			)


# ---------------------------------------------------------------------- API
def build_items(template: str, hpu_unit: str | None = None) -> list[dict]:
	"""Template rows with spec-linked limits resolved from the HPU Unit design data."""
	doc = frappe.get_cached_doc("HPU Build Inspection Template", template)
	unit = frappe.db.get_value("HPU Unit", hpu_unit, list(SPEC_LABELS), as_dict=True) if hpu_unit else None
	rows = []
	for t in doc.items:
		row = {f: t.get(f) for f in TEMPLATE_ROW_FIELDS}
		if t.numeric and t.unit_spec_field:
			nominal = flt((unit or {}).get(t.unit_spec_field))
			if nominal:
				row["min_value"] = round(nominal * (1 - flt(t.tolerance_minus_pct) / 100), 3)
				row["max_value"] = round(nominal * (1 + flt(t.tolerance_plus_pct) / 100), 3)
				row["criteria"] = f"{cstr(t.criteria)} [nominal {nominal:g}]".strip()
			else:
				row["min_value"] = row["max_value"] = None
				row["criteria"] = f"{cstr(t.criteria)} [design value {SPEC_LABELS.get(t.unit_spec_field)} missing on HPU Unit]".strip()
		rows.append(row)
	return rows


@frappe.whitelist()
def get_template_items(template: str, hpu_unit: str | None = None) -> list:
	frappe.get_cached_doc("HPU Build Inspection Template", template).check_permission("read")
	return build_items(template, hpu_unit)


@frappe.whitelist()
def get_template_instructions(template: str) -> str:
	doc = frappe.get_cached_doc("HPU Build Inspection Template", template)
	doc.check_permission("read")
	return doc.instructions or ""


@frappe.whitelist()
def make_reinspection(source_name: str, target_doc: str | dict | None = None):
	def postprocess(source, target):
		target.is_reinspection = 1
		target.reinspection_of = source.name
		target.status = "Pending"
		target.set("items", [])
		for row in build_items(target.template, target.hpu_unit):
			target.append("items", row)
		target.inspected_by = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")

	return get_mapped_doc(
		"HPU Build Inspection",
		source_name,
		{
			"HPU Build Inspection": {
				"doctype": "HPU Build Inspection",
				"validation": {"docstatus": ["=", 1], "status": ["=", "Rejected"]},
				"field_no_map": [
					"status", "non_conformance", "signature", "remarks", "inspection_date", "inspected_by",
					"inspector_name", "is_reinspection", "reinspection_of", "amended_from", "test_report", "items",
				],
			}
		},
		target_doc,
		postprocess,
	)


@frappe.whitelist()
def make_reinspection_from_nc(non_conformance: str):
	source = frappe.db.get_value("Non Conformance", non_conformance, "hpu_build_inspection")
	if not source:
		frappe.throw(_("This Non Conformance is not linked to an HPU Build Inspection."))
	return make_reinspection(source)
