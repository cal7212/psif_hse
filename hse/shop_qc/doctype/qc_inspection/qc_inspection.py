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
	CLEANLINESS_TYPES,
	CRIMP_TYPES,
	PRESSURE_TYPES,
	add_used_instruments,
	check_listed_instruments,
	instrument_types,
	listed_instruments,
	needs_instrument,
	pick,
)
from hse.shop_qc.doctype.qc_unit.qc_unit import format_iso_code, hose_spec, iso_within
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
CRIMP_IN, CRIMP_OUT = "In Spec", "Out of Spec"
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


def crimp_status(row) -> str:
	"""In Spec / Out of Spec once both ends are measured; Out of Spec as soon as either end is."""
	if not (flt(row.crimp_min) or flt(row.crimp_max)):
		return ""
	measured = [flt(v) for v in (row.crimp_a, row.crimp_b) if flt(v)]
	if any(not (flt(row.crimp_min) <= v <= flt(row.crimp_max)) for v in measured):
		return CRIMP_OUT
	return CRIMP_IN if len(measured) == 2 else ""


def cleanliness_status(row) -> str:
	"""In Spec / Out of Spec once the actual ISO 4406 code is entered against a requirement."""
	if not cstr(row.cleanliness_spec).strip() or not cstr(row.cleanliness_actual).strip():
		return ""
	return CRIMP_IN if iso_within(row.cleanliness_actual, row.cleanliness_spec) else CRIMP_OUT


def evaluate_hose(row) -> str | None:
	"""Pass/Fail for one hose once every required entry is made; None while incomplete.
	An out-of-spec crimp or cleanliness fails the hose straight away."""
	crimp = crimp_status(row)
	clean = cleanliness_status(row)
	if CRIMP_OUT in (crimp, clean):
		return FAIL
	if not row.leak_check or not flt(row.pressure_reached):
		return None
	if cstr(row.cleanliness_spec).strip() and not clean:
		return None
	if (flt(row.crimp_min) or flt(row.crimp_max)) and not crimp:
		return None
	if flt(row.hold_spec_min) and not flt(row.hold_actual_min):
		return None
	ok = row.leak_check == "No Leak" and flt(row.pressure_reached) >= flt(row.test_pressure_spec)
	if flt(row.hold_spec_min):
		ok = ok and flt(row.hold_actual_min) >= flt(row.hold_spec_min)
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


def evaluate_proof(row) -> str | None:
	"""Pass when there is no leak and each required proof pressure is reached; None while incomplete."""
	if not row.leak_check or not flt(row.p1_psi):
		return None
	if flt(row.p2_spec) and not flt(row.p2_psi):
		return None
	ok = row.leak_check == "No Leak" and flt(row.p1_psi) >= flt(row.p1_spec)
	if flt(row.p2_spec):
		ok = ok and flt(row.p2_psi) >= flt(row.p2_spec)
	return PASS if ok else FAIL


def evaluate_accumulator(row) -> str | None:
	"""Pre-charge against design when the unit has a setting tolerance; None = inspector decides."""
	tol = flt(row.tolerance_psi)
	if not tol or not flt(row.precharge_spec):
		return None
	if not flt(row.precharge_actual):
		return ""
	return PASS if abs(flt(row.precharge_actual) - flt(row.precharge_spec)) <= tol else FAIL


COATING_LAYERS = ("Surface Conditioning", "Base Coat / Primer", "Intermediate Coat", "Top Coat", "Sealer")


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
		self.load_stage_tests()
		self.refresh_hose_specs()
		self.evaluate_numeric_readings()
		self.evaluate_hose_tests()
		self.evaluate_pmg_tests()
		self.evaluate_circuit_tests()
		self.sync_instruments()
		if self.docstatus == 0:
			self.status = "Pending"

	def load_stage_tests(self):
		"""Fill the stage's test tables from the unit when they are empty."""
		if not self.hose_tests and self.is_hose_test_stage():
			self.set_hose_tests()
		if not self.pmg_tests and self.is_pmg_test_stage():
			self.set_pmg_tests()
		if self.is_pmg_test_stage() and not (self.device_tests or self.accumulator_tests):
			self.set_circuit_tests()
		if not self.proof_tests and self.is_flag_stage("proof_test"):
			self.set_proof_tests()
		if not self.coating_layers and self.is_flag_stage("coating_record"):
			for layer in COATING_LAYERS:
				self.append("coating_layers", {"layer": layer})

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

	def refresh_hose_specs(self):
		"""While in draft, keep each hose row's limits in step with the unit, so a spec
		entered or corrected on the unit after the rows were loaded is picked up on save."""
		if self.docstatus != 0 or not self.hose_tests or not self.qc_unit:
			return
		specs = {r["hose_tag"]: r for r in build_hose_tests(self.qc_unit)}
		for row in self.hose_tests:
			spec = specs.get(row.hose_tag)
			if not spec:
				continue
			for field in HOSE_SPEC_FIELDS:
				row.set(field, spec.get(field))

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

	def is_flag_stage(self, flag: str) -> bool:
		return bool(self.stage and frappe.get_cached_value("QC Stage", self.stage, flag))

	def previous_failures(self, child: str, field: str) -> set | None:
		"""Keys of rows that failed in the inspection this one re-inspects; None = load everything."""
		if not (self.is_reinspection and self.reinspection_of):
			return None
		return set(
			frappe.get_all(
				child,
				filters={"parent": self.reinspection_of, "parenttype": "QC Inspection", "result": FAIL},
				pluck=field,
			)
		)

	def set_circuit_tests(self):
		pmg_tags = {g.pmg_tag for g in self.pmg_tests}
		failed_devices = self.previous_failures("QC Device Test", "description")
		failed_accs = self.previous_failures("QC Accumulator Test", "description")
		devices, accumulators = build_circuit_tests(self.qc_unit)
		self.set("device_tests", [])
		self.set("accumulator_tests", [])
		for row in devices:
			if failed_devices is None or row["description"] in failed_devices or row["pmg_tag"] in pmg_tags:
				self.append("device_tests", row)
		for row in accumulators:
			if failed_accs is None or row["description"] in failed_accs or row["pmg_tag"] in pmg_tags:
				self.append("accumulator_tests", row)

	def set_proof_tests(self):
		failed = self.previous_failures("QC Proof Test", "description")
		for row in build_proof_tests(self.qc_unit):
			if failed is None or row["description"] in failed:
				self.append("proof_tests", row)

	def evaluate_circuit_tests(self):
		for row in self.accumulator_tests:
			if row.result == NA:
				continue
			result = evaluate_accumulator(row)
			if result is not None:
				row.result = result or None
		for row in self.proof_tests:
			row.result = evaluate_proof(row)

	def evaluate_pmg_tests(self):
		for row in self.pmg_tests:
			if row.result == NA:
				continue
			result = evaluate_pmg(row)
			if result is not None:
				row.result = result or None

	def evaluate_hose_tests(self):
		for row in self.hose_tests:
			row.cleanliness_actual = format_iso_code(row.cleanliness_actual)
			row.crimp_status = crimp_status(row)
			row.cleanliness_status = cleanliness_status(row)
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
				errors.append(
					_(
						"Hose {0}: enter both crimp diameters, the pressure reached, the hold time, the leak check and the ISO cleanliness when required."
					).format(row.hose_tag)
				)
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
		errors += self.circuit_test_errors()
		if (
			self.is_pmg_test_stage()
			and not self.pmg_tests
			and frappe.db.get_value("QC Unit", self.qc_unit, "product_type") == "Power Unit"
		):
			errors.append(_("This stage tests each pump/motor group, but the unit has none listed."))
		if errors:
			frappe.throw("<br>".join(errors), title=_("Inspection Incomplete"))

	def circuit_test_errors(self) -> list:
		errors = []
		for row in self.device_tests:
			label = row.description or row.bom_item or _("row {0}").format(row.idx)
			if row.result != NA and not cstr(row.as_set).strip():
				errors.append(_("Device {0}: enter the as-set adjustment.").format(label))
			if not row.result:
				errors.append(_("Device {0}: select the result.").format(label))
			elif row.result in (FAIL, NA) and not cstr(row.comment).strip():
				errors.append(_("Device {0}: a comment is required for {1}.").format(label, row.result))
		for row in self.accumulator_tests:
			label = row.description or row.bom_item or _("row {0}").format(row.idx)
			if row.result != NA and not flt(row.precharge_actual):
				errors.append(_("Accumulator {0}: enter the actual pre-charge.").format(label))
			if not row.result:
				errors.append(_("Accumulator {0}: select the result.").format(label))
			elif row.result in (FAIL, NA) and not cstr(row.comment).strip():
				errors.append(_("Accumulator {0}: a comment is required for {1}.").format(label, row.result))
		for row in self.proof_tests:
			label = row.description or _("row {0}").format(row.idx)
			missing = [
				row.meta.get_label(f)
				for f in ("p1_psi", "p1_media", "p1_duration_min", "leak_check")
				if not row.get(f)
			]
			if flt(row.p2_spec) and not flt(row.p2_psi):
				missing.append(row.meta.get_label("p2_psi"))
			if missing:
				errors.append(_("Proof test {0}: enter {1}.").format(label, ", ".join(missing)))
			elif row.result == FAIL and not cstr(row.finding).strip():
				errors.append(
					_("Proof test {0}: a finding is required for a failed proof test.").format(label)
				)
		if self.is_flag_stage("proof_test") and not self.proof_tests:
			if frappe.db.get_value("QC Unit", self.qc_unit, "test_hydrostatic"):
				errors.append(_("The order calls for a hydrostatic test: add the proof test record rows."))
		applied = 0
		for row in self.coating_layers:
			if not row.applied:
				errors.append(_("Coating {0}: mark it Applied or N/A.").format(row.layer))
				continue
			if row.applied != "Yes":
				continue
			applied += 1
			missing = [
				row.meta.get_label(f) for f in ("product_type", "brand", "product_code") if not row.get(f)
			]
			if row.layer != "Surface Conditioning" and not flt(row.mil_thickness):
				missing.append(row.meta.get_label("mil_thickness"))
			if missing:
				errors.append(_("Coating {0}: enter {1}.").format(row.layer, ", ".join(missing)))
		if self.coating_layers and not applied:
			errors.append(_("Coating Application Record: at least one layer must be applied."))
		return errors

	def check_test_equipment(self):
		"""Every reading names an instrument; every instrument is Active and in calibration."""
		needs = (
			self.hose_tests
			or self.pmg_tests
			or self.accumulator_tests
			or self.proof_tests
			or any(needs_instrument(r) for r in self.items)
		)
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
		for a in self.accumulator_tests:
			if flt(a.precharge_actual) and not a.instrument:
				errors.append(
					_("Accumulator {0}: select the pre-charge gauge.").format(a.description or a.idx)
				)
		for p in self.proof_tests:
			if flt(p.p1_psi) and not p.instrument:
				errors.append(
					_("Proof test {0}: select the pressure instrument.").format(p.description or p.idx)
				)
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
			if not h.particle_counter and h.cleanliness_actual:
				h.particle_counter = pick(names, types, CLEANLINESS_TYPES)
		for g in self.pmg_tests:
			if not g.instrument and (flt(g.relief_as_set) or flt(g.compensator_as_set)):
				g.instrument = pick(names, types, PRESSURE_TYPES)
			if not g.amps_instrument and flt(g.motor_amps):
				g.amps_instrument = pick(names, types, AMPS_TYPES)
		for row in self.accumulator_tests:
			if not row.instrument and flt(row.precharge_actual):
				row.instrument = pick(names, types, PRESSURE_TYPES)
		for row in self.proof_tests:
			if not row.instrument and flt(row.p1_psi):
				row.instrument = pick(names, types, PRESSURE_TYPES)
		used = [r.instrument for r in self.items]
		for h in self.hose_tests:
			used += [h.instrument, h.crimp_instrument, h.particle_counter]
		for g in self.pmg_tests:
			used += [g.instrument, g.amps_instrument]
		used += [r.instrument for r in self.accumulator_tests] + [r.instrument for r in self.proof_tests]
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
			+ [r for r in self.device_tests if r.result == FAIL]
			+ [r for r in self.accumulator_tests if r.result == FAIL]
			+ [r for r in self.proof_tests if r.result == FAIL]
		)

	def create_non_conformance(self):
		failed = [r for r in self.items if r.result == FAIL]
		failed_hoses = [h for h in self.hose_tests if h.result == FAIL]
		failed_pmgs = [g for g in self.pmg_tests if g.result == FAIL]
		# A failed hose pressure test or a wrong relief/compensator setting is always critical.
		failed_other = (
			[
				(_("Device"), r.description, r.as_set, r.design_setting, r.comment)
				for r in self.device_tests
				if r.result == FAIL
			]
			+ [
				(_("Accumulator"), r.description, r.precharge_actual, r.precharge_spec, r.comment)
				for r in self.accumulator_tests
				if r.result == FAIL
			]
			+ [
				(_("Proof test"), r.description, f"{r.p1_psi} / {r.leak_check}", r.p1_spec, r.finding)
				for r in self.proof_tests
				if r.result == FAIL
			]
		)
		# Pressure-containing failures are always critical.
		critical = (
			any(r.is_critical for r in failed)
			or bool(failed_hoses)
			or bool(failed_pmgs)
			or any(r.result == FAIL for r in self.proof_tests)
		)

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
				"<tr><td>{0}</td><td>{1}</td><td>{2} / {3} ({4} - {5}) {6}</td><td>{7} ({8})</td><td>{9} ({10})</td><td>{11}</td><td>{13} ({14}) {15}</td><td>{12}</td></tr>".format(
					escape_html(cstr(h.hose_tag)),
					escape_html(" ".join(x for x in (cstr(h.spec_basis), cstr(h.spec_reference)) if x)),
					cstr(h.crimp_a or ""),
					cstr(h.crimp_b or ""),
					cstr(h.crimp_min or ""),
					cstr(h.crimp_max or ""),
					escape_html(_(h.crimp_status) if h.crimp_status else ""),
					cstr(h.pressure_reached or ""),
					cstr(h.test_pressure_spec or ""),
					cstr(h.hold_actual_min or ""),
					cstr(h.hold_spec_min or ""),
					escape_html(cstr(h.leak_check)),
					escape_html(cstr(h.finding)),
					escape_html(cstr(h.cleanliness_actual)),
					escape_html(cstr(h.cleanliness_spec)),
					escape_html(_(h.cleanliness_status) if h.cleanliness_status else ""),
				)
				for h in failed_hoses
			)
			details += (
				f"<p><b>{_('Failed hoses')}</b></p><table class='table table-bordered'><thead><tr>"
				f"<th>{_('Hose Tag')}</th><th>{_('Spec')}</th><th>{_('Crimp A / B (limits)')}</th>"
				f"<th>{_('Pressure psi (required)')}</th><th>{_('Hold min (required)')}</th>"
				f"<th>{_('Leak Check')}</th><th>{_('ISO Cleanliness (required)')}</th>"
				f"<th>{_('Finding')}</th></tr></thead><tbody>{hose_rows}</tbody></table>"
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
		if failed_other:
			other_rows = "".join(
				"<tr>"
				+ "".join(f"<td>{escape_html(cstr(v if v is not None else ''))}</td>" for v in row)
				+ "</tr>"
				for row in failed_other
			)
			details += (
				f"<p><b>{_('Failed devices, accumulators and proof tests')}</b></p>"
				f"<table class='table table-bordered'><thead><tr><th>{_('Type')}</th><th>{_('Description')}</th>"
				f"<th>{_('As found / as-set')}</th><th>{_('Design')}</th><th>{_('Finding')}</th></tr></thead>"
				f"<tbody>{other_rows}</tbody></table>"
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
		for h in failed_hoses:
			h.db_set("non_conformance", nc.name)
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
		spec = hose_spec(h, unit.target_cleanliness)
		diameter, tol = spec.crimp_diameter, spec.crimp_tolerance
		rows.append(
			{
				"hose_tag": h.hose_tag,
				"part_number": h.part_number,
				"hose_type": h.hose_type,
				"die_size": h.die_size,
				"spec_basis": spec.basis,
				"spec_reference": spec.reference,
				"crimp_min": round(diameter - tol, 4) if diameter else None,
				"crimp_max": round(diameter + tol, 4) if diameter else None,
				"test_pressure_spec": spec.test_pressure,
				"hold_spec_min": spec.hold_min,
				"cleanliness_spec": spec.cleanliness,
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
				"theoretical_flow_gpm": g.design_flow_gpm,
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


HOSE_SPEC_FIELDS = (
	"part_number",
	"hose_type",
	"die_size",
	"spec_basis",
	"spec_reference",
	"crimp_min",
	"crimp_max",
	"test_pressure_spec",
	"hold_spec_min",
	"cleanliness_spec",
)
STAGE_TABLES = (
	"hose_tests",
	"pmg_tests",
	"device_tests",
	"accumulator_tests",
	"proof_tests",
	"coating_layers",
)


@frappe.whitelist()
def get_stage_test_rows(
	qc_unit: str, stage: str, is_reinspection: int = 0, reinspection_of: str | None = None
) -> dict:
	"""Test rows a new inspection of this stage starts with, so the form can show them before
	the first save. Uses the same loaders as validate()."""
	frappe.has_permission("QC Inspection", "create", throw=True)
	frappe.has_permission("QC Unit", "read", qc_unit, throw=True)
	doc = frappe.new_doc("QC Inspection")
	doc.update(
		{
			"qc_unit": qc_unit,
			"stage": stage,
			"is_reinspection": cint(is_reinspection),
			"reinspection_of": reinspection_of,
		}
	)
	doc.load_stage_tests()
	return {table: [row.as_dict(no_default_fields=True) for row in doc.get(table)] for table in STAGE_TABLES}


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
def build_circuit_tests(qc_unit: str) -> tuple[list[dict], list[dict]]:
	"""Device and accumulator test rows from the unit's circuit lists."""
	unit = frappe.get_doc("QC Unit", qc_unit)
	if unit.product_type != "Power Unit":
		return [], []
	devices = [
		{
			"pmg_tag": d.pmg_tag,
			"bom_item": d.bom_item,
			"description": d.description,
			"design_setting": d.design_setting,
		}
		for d in unit.circuit_devices
	]
	accumulators = [
		{
			"pmg_tag": a.pmg_tag,
			"bom_item": a.bom_item,
			"description": a.description,
			"serial_no": a.serial_no,
			"volume_gal": a.volume_gal,
			"precharge_spec": a.precharge_psi,
			"tolerance_psi": unit.setting_tolerance_psi,
		}
		for a in unit.accumulators
	]
	return devices, accumulators


def build_proof_tests(qc_unit: str) -> list[dict]:
	unit = frappe.get_doc("QC Unit", qc_unit)
	return [
		{
			"bom_item": p.bom_item,
			"description": p.description or p.bom_item,
			"serial_no": p.serial_no,
			"p1_spec": p.p1_psi,
			"p2_spec": p.p2_psi,
		}
		for p in unit.proof_test_items
	]


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
		for table in ("device_tests", "accumulator_tests", "proof_tests", "coating_layers"):
			target.set(table, [])
		if target.is_pmg_test_stage():
			target.set_circuit_tests()
		if target.is_flag_stage("proof_test"):
			target.set_proof_tests()
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
					"device_tests",
					"accumulator_tests",
					"proof_tests",
					"coating_layers",
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
