# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.model.naming import make_autoname
from frappe.utils import cint, cstr, escape_html, flt, getdate

from hse.hse.instruments import (
	AMPS_TYPES,
	CRIMP_TYPES,
	PRESSURE_TYPES,
	add_used_instruments,
	check_listed_instruments,
	instrument_types,
	listed_instruments,
	needs_instrument,
	pick,
)
from hse.shop_qc.utils import (
	LOCKED_STATUSES,
	count_open_ncs,
	get_accepted_by_stage,
	get_stages,
	get_unit_context,
	stage_applies,
	template_matches,
	update_unit_status,
)

PASS, FAIL, NA = "Pass", "Fail", "N/A"
TEMPLATE_ROW_FIELDS = (
	"check_item",
	"criteria",
	"is_critical",
	"requires_photo",
	"numeric",
	"record_text",
	"min_value",
	"max_value",
	"uom",
	"unit_spec_field",
)
SPEC_LABELS = {
	"relief_setting_psi": "Relief Setting (psi)",
	"max_operating_psi": "Max Operating Pressure (psi)",
	"proof_test_psi": "Proof Test Pressure (psi)",
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


def evaluate_hose(row) -> str | None:
	"""Pass/Fail for one hose once every required entry is made; None while incomplete."""
	if not row.leak_check or not flt(row.pressure_reached):
		return None
	crimp_spec = flt(row.crimp_min) or flt(row.crimp_max)
	if crimp_spec and not (flt(row.crimp_a) and flt(row.crimp_b)):
		return None
	if cint(row.hold_time_spec) and not cint(row.hold_time_actual):
		return None
	ok = row.leak_check == "No Leak" and flt(row.pressure_reached) >= flt(row.test_pressure_spec)
	if cint(row.hold_time_spec):
		ok = ok and cint(row.hold_time_actual) >= cint(row.hold_time_spec)
	if crimp_spec:
		for v in (flt(row.crimp_a), flt(row.crimp_b)):
			ok = ok and flt(row.crimp_min) <= v <= flt(row.crimp_max)
	return PASS if ok else FAIL


def evaluate_pmg(row) -> str | None:
	"""Pass/Fail for one pump/motor group. A "No" answer always fails. Settings are judged
	against the design value only when the unit has a setting tolerance; otherwise the
	inspector's result stands (None = leave it)."""
	if row.nameplate_verified == "No" or row.rotation_verified == "No":
		return FAIL
	tol = flt(row.tolerance_psi)
	if not tol:
		return None
	pairs = [
		(flt(row.relief_spec), flt(row.relief_as_set)),
		(flt(row.compensator_spec), flt(row.compensator_as_set)),
	]
	if not (row.nameplate_verified and row.rotation_verified):
		return ""
	if any(spec and not actual for spec, actual in pairs):
		return ""
	ok = all(abs(actual - spec) <= tol for spec, actual in pairs if spec)
	return PASS if ok else FAIL


class QCInspection(Document):
	def autoname(self):
		shop = self.shop or frappe.db.get_value("QC Unit", self.qc_unit, "shop")
		prefix = frappe.db.get_value("Build Shop", shop, "inspection_prefix") if shop else None
		self.name = make_autoname(f"{(prefix or 'QCI').strip().upper()}-.YYYY.-.#####", doc=self)

	# ------------------------------------------------------------------ validate
	def validate(self):
		self.validate_unit()
		self.validate_template()
		self.validate_reinspection()
		if not self.items:
			self.set_items_from_template()
		if not self.hose_tests and self.is_hose_test_stage():
			self.set_hose_tests()
		if not self.pmg_tests and self.is_pmg_test_stage():
			self.set_pmg_tests()
		self.evaluate_numeric_readings()
		self.evaluate_hose_tests()
		self.evaluate_pmg_tests()
		self.sync_instruments()
		if self.docstatus == 0:
			self.status = "Pending"

	def validate_unit(self):
		status = frappe.db.get_value("QC Unit", self.qc_unit, "status")
		if status in LOCKED_STATUSES:
			frappe.throw(
				_("QC Unit {0} is {1}; no further build inspections can be recorded.").format(
					frappe.bold(self.qc_unit), status
				)
			)
		stage = frappe.get_cached_doc("QC Stage", self.stage)
		if stage.disabled:
			frappe.throw(_("QC Stage {0} is disabled.").format(frappe.bold(self.stage)))
		ctx = get_unit_context(self.qc_unit)
		if not stage_applies(stage, ctx.shop, ctx.job_type):
			frappe.throw(
				_("QC Stage {0} does not apply to {1} {2} units.").format(
					frappe.bold(self.stage), ctx.shop or "", (ctx.job_type or "").lower()
				)
			)
		self.stage_sequence = stage.sequence

	def validate_template(self):
		t = frappe.get_cached_doc("QC Inspection Template", self.template)
		if t.disabled:
			frappe.throw(_("Inspection Template {0} is disabled.").format(frappe.bold(self.template)))
		if t.stage != self.stage:
			frappe.throw(
				_("Template {0} is for stage {1}, not {2}.").format(
					frappe.bold(self.template), frappe.bold(t.stage), frappe.bold(self.stage)
				)
			)
		ctx = get_unit_context(self.qc_unit)
		if not template_matches(t, ctx.product_type, ctx.model):
			frappe.throw(
				_("Template {0} is for {1}; this unit is a {2}, model {3}.").format(
					frappe.bold(self.template),
					" ".join(x for x in (t.product_type, t.model_prefix and f"{t.model_prefix}*") if x),
					ctx.product_type,
					ctx.model,
				)
			)
		if not self.quality_procedure:
			self.quality_procedure = t.quality_procedure or (
				frappe.db.get_value("Build Shop", ctx.shop, "quality_procedure") if ctx.shop else None
			)

	def validate_reinspection(self):
		if not self.is_reinspection:
			self.reinspection_of = None
			return
		if not self.reinspection_of:
			frappe.throw(_("Select the original inspection in Re-inspection Of."))
		if self.reinspection_of == self.name:
			frappe.throw(_("An inspection cannot be a re-inspection of itself."))
		orig = frappe.db.get_value(
			"QC Inspection",
			self.reinspection_of,
			["qc_unit", "stage", "status", "docstatus"],
			as_dict=True,
		)
		if not orig or orig.docstatus != 1 or orig.status != "Rejected":
			frappe.throw(_("Re-inspection Of must be a submitted, Rejected inspection."))
		if orig.qc_unit != self.qc_unit or orig.stage != self.stage:
			frappe.throw(
				_("A re-inspection must be for the same QC Unit ({0}) and stage ({1}).").format(
					frappe.bold(orig.qc_unit), frappe.bold(orig.stage)
				)
			)

	def set_items_from_template(self):
		self.set("items", [])
		for row in build_items(self.template, self.qc_unit):
			self.append("items", row)

	def is_hose_test_stage(self) -> bool:
		return bool(self.stage and frappe.get_cached_value("QC Stage", self.stage, "hose_test"))

	def set_hose_tests(self):
		tags = None
		if self.is_reinspection and self.reinspection_of:
			# Re-test only the hoses that failed last time
			tags = set(
				frappe.get_all(
					"QC Hose Test",
					filters={"parent": self.reinspection_of, "parenttype": "QC Inspection", "result": FAIL},
					pluck="hose_tag",
				)
			)
		self.set("hose_tests", [])
		for row in build_hose_tests(self.qc_unit, tags):
			self.append("hose_tests", row)

	def is_pmg_test_stage(self) -> bool:
		return bool(self.stage and frappe.get_cached_value("QC Stage", self.stage, "pmg_test"))

	def set_pmg_tests(self):
		tags = None
		if self.is_reinspection and self.reinspection_of:
			# Re-test only the groups that failed last time
			tags = set(
				frappe.get_all(
					"QC PMG Test",
					filters={"parent": self.reinspection_of, "parenttype": "QC Inspection", "result": FAIL},
					pluck="pmg_tag",
				)
			)
		self.set("pmg_tests", [])
		for row in build_pmg_tests(self.qc_unit, tags):
			self.append("pmg_tests", row)

	def evaluate_pmg_tests(self):
		for row in self.pmg_tests:
			if row.result == NA:
				continue
			result = evaluate_pmg(row)
			if result is not None:
				row.result = result or None

	def evaluate_hose_tests(self):
		for row in self.hose_tests:
			row.result = evaluate_hose(row)

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
				errors.append(
					_(
						"Row {0}: '{1}' takes its limits from {2}, which is blank on QC Unit {3}. "
						"Enter the design value on the unit and reload the checklist."
					).format(
						row.idx,
						label,
						SPEC_LABELS.get(row.unit_spec_field, row.unit_spec_field),
						self.qc_unit,
					)
				)
			if row.record_text and not cstr(row.text_value).strip():
				errors.append(_("Row {0}: Record the value for '{1}'.").format(row.idx, label))
			if row.requires_photo and not row.photo:
				errors.append(_("Row {0}: A photo is required for '{1}'.").format(row.idx, label))
		for row in self.hose_tests:
			if not flt(row.test_pressure_spec):
				errors.append(
					_(
						"Hose {0}: no test pressure on the unit. Enter it (or the shop's multiplier) and reload."
					).format(row.hose_tag)
				)
			elif not row.result:
				errors.append(_("Hose {0}: enter every test value and the leak check.").format(row.hose_tag))
			elif row.result == FAIL and not cstr(row.finding).strip():
				errors.append(_("Hose {0}: a finding is required for a failed hose.").format(row.hose_tag))
		if self.is_hose_test_stage() and not self.hose_tests:
			errors.append(_("This stage tests each hose, but the unit has no tagged hoses."))
		for row in self.pmg_tests:
			tag = row.pmg_tag
			if row.result == NA:
				if not cstr(row.finding).strip():
					errors.append(_("{0}: say why this pump/motor group is N/A in the finding.").format(tag))
				continue
			if not flt(row.relief_spec):
				errors.append(
					_("{0}: no relief valve setting on the unit. Enter it on the QC Unit and reload.").format(
						tag
					)
				)
			if not row.nameplate_verified:
				errors.append(_("{0}: confirm whether the nameplates match.").format(tag))
			if not row.rotation_verified:
				errors.append(_("{0}: confirm the rotation.").format(tag))
			if flt(row.relief_spec) and not flt(row.relief_as_set):
				errors.append(_("{0}: enter the relief as-set pressure.").format(tag))
			if flt(row.compensator_spec) and not flt(row.compensator_as_set):
				errors.append(_("{0}: enter the compensator as-set pressure.").format(tag))
			if not row.result:
				errors.append(_("{0}: select the result.").format(tag))
			elif row.result == FAIL and not cstr(row.finding).strip():
				errors.append(_("{0}: a finding is required for a failed pump/motor group.").format(tag))
		if (
			self.is_pmg_test_stage()
			and not self.pmg_tests
			and frappe.db.get_value("QC Unit", self.qc_unit, "product_type") == "Power Unit"
		):
			errors.append(_("This stage tests each pump/motor group, but the unit has none listed."))
		if errors:
			frappe.throw("<br>".join(errors), title=_("Inspection Incomplete"))

	def check_test_equipment(self):
		"""Every reading names an instrument; every instrument is Active and in calibration."""
		needs = self.hose_tests or self.pmg_tests or any(needs_instrument(r) for r in self.items)
		if not needs and not self.instruments:
			return
		if not self.instruments:
			frappe.throw(_("Add the test equipment used for the numeric readings and pressure tests."))
		errors = check_listed_instruments(self, self.inspection_date)
		for r in self.items:
			if needs_instrument(r) and flt(r.reading_value) and not r.instrument:
				errors.append(_("Row {0}: select the instrument used for '{1}'.").format(r.idx, r.check_item))
		for h in self.hose_tests:
			if not h.instrument:
				errors.append(_("Hose {0}: select the pressure instrument.").format(h.hose_tag))
			if (flt(h.crimp_min) or flt(h.crimp_max)) and not h.crimp_instrument:
				errors.append(_("Hose {0}: select the crimp measuring instrument.").format(h.hose_tag))
		for g in self.pmg_tests:
			if g.result == NA:
				continue
			if (flt(g.relief_as_set) or flt(g.compensator_as_set)) and not g.instrument:
				errors.append(_("{0}: select the pressure instrument.").format(g.pmg_tag))
			if flt(g.motor_amps) and not g.amps_instrument:
				errors.append(_("{0}: select the instrument used for running amps.").format(g.pmg_tag))
		if errors:
			frappe.throw("<br>".join(errors), title=_("Test Equipment"))

	def sync_instruments(self):
		"""Default the per-reading instrument when the choice is obvious, and list every
		instrument a reading uses in the Test Equipment table."""
		names = listed_instruments(self)
		types = instrument_types(names)
		only = pick(names, types)
		for r in self.items:
			if needs_instrument(r) and not r.instrument and only:
				r.instrument = only
		for h in self.hose_tests:
			if not h.instrument:
				h.instrument = pick(names, types, PRESSURE_TYPES)
			if not h.crimp_instrument and (flt(h.crimp_min) or flt(h.crimp_max)):
				h.crimp_instrument = pick(names, types, CRIMP_TYPES)
		for g in self.pmg_tests:
			if not g.instrument and (flt(g.relief_as_set) or flt(g.compensator_as_set)):
				g.instrument = pick(names, types, PRESSURE_TYPES)
			if not g.amps_instrument and flt(g.motor_amps):
				g.amps_instrument = pick(names, types, AMPS_TYPES)
		used = [r.instrument for r in self.items]
		for h in self.hose_tests:
			used += [h.instrument, h.crimp_instrument]
		for g in self.pmg_tests:
			used += [g.instrument, g.amps_instrument]
		add_used_instruments(self, used)

	def check_hold_points(self):
		stage = frappe.get_cached_doc("QC Stage", self.stage)
		if not stage.hold_point:
			return
		accepted = get_accepted_by_stage(self.qc_unit)
		missing = [
			s.name
			for s in get_stages(self.qc_unit, required_only=True)
			if s.sequence < stage.sequence and s.name not in accepted
		]
		if missing:
			frappe.throw(
				_("Hold point: these earlier stages must be Accepted first: {0}").format(", ".join(missing)),
				title=_("Hold Point"),
			)

	def check_not_already_accepted(self):
		existing = frappe.db.get_value(
			"QC Inspection",
			{
				"qc_unit": self.qc_unit,
				"stage": self.stage,
				"docstatus": 1,
				"status": "Accepted",
				"name": ("!=", self.name),
			},
			"name",
		)
		if existing:
			frappe.throw(
				_(
					"Stage {0} is already Accepted for this unit ({1}). Cancel that inspection first if it must be repeated."
				).format(frappe.bold(self.stage), frappe.get_desk_link("QC Inspection", existing))
			)

	def check_release_allowed(self):
		unit = frappe.db.get_value(
			"QC Unit",
			self.qc_unit,
			["job_type", "failure_cause", "work_performed", "disposition"],
			as_dict=True,
		)
		if unit.job_type == "Repair":
			missing = [
				label
				for field, label in (
					("failure_cause", _("Failure Cause")),
					("work_performed", _("Work Performed")),
					("disposition", _("Disposition")),
				)
				if not unit.get(field)
			]
			if missing:
				frappe.throw(
					_("Complete these on repair {0} before final release: {1}").format(
						frappe.bold(self.qc_unit), ", ".join(missing)
					),
					title=_("Release Blocked"),
				)
		open_ncs = count_open_ncs(self.qc_unit)
		if open_ncs:
			frappe.throw(
				_("QC Unit {0} has {1} open Non Conformance(s). Resolve them before final release.").format(
					frappe.bold(self.qc_unit), open_ncs
				),
				title=_("Release Blocked"),
			)

	def on_submit(self):
		if self.status == "Rejected":
			self.create_non_conformance()
		else:
			self.link_reinspection_to_original_nc()
		update_unit_status(self.qc_unit)

	def before_cancel(self):
		if frappe.db.get_value("QC Unit", self.qc_unit, "status") == "Shipped":
			frappe.throw(
				_("QC Unit {0} has shipped; its build inspections cannot be cancelled.").format(
					frappe.bold(self.qc_unit)
				)
			)
		if self.status == "Accepted":
			later = frappe.get_all(
				"QC Inspection",
				filters={
					"qc_unit": self.qc_unit,
					"docstatus": 1,
					"status": "Accepted",
					"stage_sequence": (">", self.stage_sequence or 0),
				},
				pluck="name",
			)
			if later:
				frappe.throw(
					_("Later stages were accepted after this one ({0}). Cancel those first.").format(
						", ".join(later)
					)
				)

	def on_cancel(self):
		# Must be set on the instance: lets the inspection be cancelled even though
		# its Non Conformance / re-inspection link back to it.
		self.ignore_linked_doctypes = ("Non Conformance", "QC Inspection", "QC Unit")
		self.db_set("status", "Pending")
		if self.non_conformance:
			nc = frappe.get_doc("Non Conformance", self.non_conformance)
			if nc.status == "Open":
				nc.status = "Cancelled"
				nc.flags.ignore_permissions = True
				nc.add_comment(
					"Info", _("Cancelled because QC Inspection {0} was cancelled.").format(self.name)
				)
				nc.save()
		if self.is_reinspection and self.reinspection_of:
			orig_nc = frappe.db.get_value("QC Inspection", self.reinspection_of, "non_conformance")
			if orig_nc and frappe.db.get_value("Non Conformance", orig_nc, "qc_reinspection") == self.name:
				if frappe.db.get_value("Non Conformance", orig_nc, "status") == "Resolved":
					frappe.throw(
						_(
							"Non Conformance {0} was resolved using this re-inspection. Reopen it before cancelling."
						).format(frappe.bold(orig_nc))
					)
				frappe.db.set_value("Non Conformance", orig_nc, "qc_reinspection", None)
		update_unit_status(self.qc_unit)

	# ------------------------------------------------------------------ helpers
	def is_final_release(self) -> bool:
		return bool(frappe.get_cached_value("QC Stage", self.stage, "is_final_release"))

	def get_failed_rows(self):
		return (
			[r for r in self.items if r.result == FAIL]
			+ [h for h in self.hose_tests if h.result == FAIL]
			+ [g for g in self.pmg_tests if g.result == FAIL]
		)

	def create_non_conformance(self):
		failed = [r for r in self.items if r.result == FAIL]
		failed_hoses = [h for h in self.hose_tests if h.result == FAIL]
		failed_pmgs = [g for g in self.pmg_tests if g.result == FAIL]
		# A failed hose pressure test or a wrong relief/compensator setting is always critical.
		critical = any(r.is_critical for r in failed) or bool(failed_hoses) or bool(failed_pmgs)

		def reading(r):
			if r.numeric:
				return escape_html(cstr(r.reading_value)) + (
					f" ({cstr(r.min_value or '')}-{cstr(r.max_value or '')})"
					if (r.min_value or r.max_value)
					else ""
				)
			return escape_html(cstr(r.text_value))

		rows = "".join(
			"<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td></tr>".format(
				escape_html(cstr(r.check_item)),
				_("Yes") if r.is_critical else _("No"),
				reading(r),
				escape_html(cstr(r.finding)),
			)
			for r in failed
		)
		details = (
			f"<p>{_('QC Unit')}: <b>{escape_html(self.qc_unit)}</b> ({escape_html(cstr(self.shop))}) - {escape_html(cstr(self.model))}"
			f" {_('S/N')} {escape_html(cstr(self.serial_no))}<br>"
			f"{_('Stage')}: <b>{escape_html(self.stage)}</b><br>"
			f"{_('Inspection')}: <b>{self.name}</b> - {self.inspection_date}<br>"
			f"{_('Inspected By')}: {escape_html(cstr(self.inspector_name or self.inspected_by))}</p>"
			f"<table class='table table-bordered'><thead><tr><th>{_('Check Item')}</th><th>{_('Critical')}</th>"
			f"<th>{_('Reading')}</th><th>{_('Finding')}</th></tr></thead><tbody>{rows}</tbody></table>"
		)
		if failed_hoses:
			hose_rows = "".join(
				"<tr><td>{0}</td><td>{1} / {2}</td><td>{3} ({4})</td><td>{5}</td><td>{6}</td></tr>".format(
					escape_html(cstr(h.hose_tag)),
					cstr(h.crimp_a or ""),
					cstr(h.crimp_b or ""),
					cstr(h.pressure_reached or ""),
					cstr(h.test_pressure_spec or ""),
					escape_html(cstr(h.leak_check)),
					escape_html(cstr(h.finding)),
				)
				for h in failed_hoses
			)
			details += (
				f"<p><b>{_('Failed hoses')}</b></p><table class='table table-bordered'><thead><tr>"
				f"<th>{_('Hose Tag')}</th><th>{_('Crimp A / B')}</th><th>{_('Pressure (required)')}</th>"
				f"<th>{_('Leak Check')}</th><th>{_('Finding')}</th></tr></thead><tbody>{hose_rows}</tbody></table>"
			)
		if failed_pmgs:
			pmg_rows = "".join(
				"<tr><td>{0}</td><td>{1} / {2}</td><td>{3} / {4}</td><td>{5}</td><td>{6}</td><td>{7}</td></tr>".format(
					escape_html(cstr(g.pmg_tag)),
					cstr(g.relief_as_set or ""),
					cstr(g.relief_spec or ""),
					cstr(g.compensator_as_set or ""),
					cstr(g.compensator_spec or ""),
					escape_html(cstr(g.nameplate_verified)),
					escape_html(cstr(g.rotation_verified)),
					escape_html(cstr(g.finding)),
				)
				for g in failed_pmgs
			)
			details += (
				f"<p><b>{_('Failed pump / motor groups')}</b></p><table class='table table-bordered'><thead><tr>"
				f"<th>{_('PMG')}</th><th>{_('Relief as-set / design')}</th><th>{_('Compensator as-set / design')}</th>"
				f"<th>{_('Nameplates')}</th><th>{_('Rotation')}</th><th>{_('Finding')}</th></tr></thead>"
				f"<tbody>{pmg_rows}</tbody></table>"
			)
		if self.remarks:
			details += f"<p>{_('Remarks')}: {escape_html(self.remarks)}</p>"

		nc = frappe.get_doc(
			{
				"doctype": "Non Conformance",
				"subject": f"{self.shop or 'QC'} QC failure - {self.qc_unit} {self.stage} ({self.name})",
				"procedure": self.quality_procedure,
				"status": "Open",
				"details": details,
				"qc_unit": self.qc_unit,
				"qc_inspection": self.name,
				"severity": "Critical" if critical else "Medium",
				"interim_control": _("Unit on QC Hold; do not pressurize, install or ship until resolved.")
				if critical
				else _("Unit on QC Hold pending corrective action."),
			}
		)
		nc.flags.ignore_permissions = True
		nc.insert()
		self.db_set("non_conformance", nc.name)
		frappe.msgprint(
			_("Non Conformance {0} created and {1} placed on QC Hold.").format(
				frappe.get_desk_link("Non Conformance", nc.name), self.qc_unit
			),
			indicator="red",
			alert=True,
		)

	def link_reinspection_to_original_nc(self):
		if not (self.is_reinspection and self.reinspection_of):
			return
		orig_nc = frappe.db.get_value("QC Inspection", self.reinspection_of, "non_conformance")
		if orig_nc:
			frappe.db.set_value("Non Conformance", orig_nc, "qc_reinspection", self.name)
			frappe.msgprint(
				_(
					"Re-inspection linked to {0}. Complete verification and resolve it to clear the QC Hold."
				).format(frappe.get_desk_link("Non Conformance", orig_nc)),
				indicator="green",
				alert=True,
			)


# ---------------------------------------------------------------------- API
def build_hose_tests(qc_unit: str, only_tags: set | None = None) -> list[dict]:
	"""One test row per tagged hose on the unit, with limits from the hose line."""
	unit = frappe.get_doc("QC Unit", qc_unit)
	rows = []
	for h in unit.hoses:
		if only_tags is not None and h.hose_tag not in only_tags:
			continue
		spec, tol = flt(h.crimp_diameter_spec), flt(h.crimp_tolerance)
		rows.append(
			{
				"hose_tag": h.hose_tag,
				"part_number": h.part_number,
				"crimp_min": round(spec - tol, 4) if spec else None,
				"crimp_max": round(spec + tol, 4) if spec else None,
				"test_pressure_spec": h.test_pressure_psi,
				"hold_time_spec": h.hold_time_sec,
			}
		)
	return rows


def build_pmg_tests(qc_unit: str, only_tags: set | None = None) -> list[dict]:
	"""One test row per pump/motor group on the unit, with its design settings."""
	unit = frappe.get_doc("QC Unit", qc_unit)
	if unit.product_type != "Power Unit":
		return []
	rows = []
	for g in unit.pump_motor_groups:
		if only_tags is not None and g.pmg_tag not in only_tags:
			continue
		rows.append(
			{
				"pmg_tag": g.pmg_tag,
				"service": g.service,
				"relief_spec": g.relief_setting_psi,
				"compensator_spec": g.compensator_setting_psi,
				"tolerance_psi": unit.setting_tolerance_psi,
				"motor_fla": g.motor_fla,
			}
		)
	return rows


def build_items(template: str, qc_unit: str | None = None) -> list[dict]:
	"""Template rows with spec-linked limits resolved from the QC Unit design data."""
	doc = frappe.get_cached_doc("QC Inspection Template", template)
	unit = frappe.db.get_value("QC Unit", qc_unit, list(SPEC_LABELS), as_dict=True) if qc_unit else None
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
				row["criteria"] = (
					f"{cstr(t.criteria)} [design value {SPEC_LABELS.get(t.unit_spec_field)} missing on the unit]".strip()
				)
		rows.append(row)
	return rows


@frappe.whitelist()
def get_template_items(template: str, qc_unit: str | None = None) -> list:
	frappe.get_cached_doc("QC Inspection Template", template).check_permission("read")
	return build_items(template, qc_unit)


@frappe.whitelist()
def get_template_instructions(template: str) -> str:
	doc = frappe.get_cached_doc("QC Inspection Template", template)
	doc.check_permission("read")
	return doc.instructions or ""


@frappe.whitelist()
def make_reinspection(source_name: str, target_doc: str | dict | None = None):
	def postprocess(source, target):
		target.is_reinspection = 1
		target.reinspection_of = source.name
		target.status = "Pending"
		target.set("items", [])
		for row in build_items(target.template, target.qc_unit):
			target.append("items", row)
		target.set("hose_tests", [])
		if target.is_hose_test_stage():
			target.set_hose_tests()
		target.set("pmg_tests", [])
		if target.is_pmg_test_stage():
			target.set_pmg_tests()
		target.inspected_by = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")

	return get_mapped_doc(
		"QC Inspection",
		source_name,
		{
			"QC Inspection": {
				"doctype": "QC Inspection",
				"validation": {"docstatus": ["=", 1], "status": ["=", "Rejected"]},
				"field_no_map": [
					"status",
					"non_conformance",
					"signature",
					"remarks",
					"inspection_date",
					"inspected_by",
					"inspector_name",
					"is_reinspection",
					"reinspection_of",
					"amended_from",
					"test_report",
					"items",
					"hose_tests",
					"pmg_tests",
					"naming_series",
				],
			}
		},
		target_doc,
		postprocess,
	)


@frappe.whitelist()
def make_reinspection_from_nc(non_conformance: str):
	source = frappe.db.get_value("Non Conformance", non_conformance, "qc_inspection")
	if not source:
		frappe.throw(_("This Non Conformance is not linked to a QC Inspection."))
	return make_reinspection(source)
