# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""QM-400 controls on the QC Unit that sit around the build and its release.

- 8.5.1 Build package release: Operations releases the drawings and BOM to the floor before
  stages flagged Requires Build Package Release can be completed.
- 8.6 Cross-functional release: on shops with Cross-Functional Release, a new-build system unit
  is Released only when the final release inspection is accepted (Quality) and Project
  Management / Sales, Operations and Accounting have each confirmed.
- 4.2.1 / 7.2 / 8.5.2 Welding, in two tiers set by the unit's Welding Standard:
  a code required by design or the customer brings full material and filler-metal
  traceability (Material Test Reports required) and code-qualified welders; PSIF workmanship
  (no code) needs only welders holding the in-house welding authorization.
"""

import frappe
from frappe import _
from frappe.utils import cstr, get_datetime, getdate, now_datetime

PM_SALES, OPERATIONS, ACCOUNTING = "Project Management / Sales", "Operations / Production", "Accounting"
RELEASE_FUNCTIONS = (PM_SALES, OPERATIONS, ACCOUNTING)
# Roles that may confirm for each function. System Manager is the administrator's way in.
CONFIRM_ROLES = {
	PM_SALES: ("Projects Manager", "Projects User", "Sales Manager", "Sales User", "System Manager"),
	OPERATIONS: ("Manufacturing Manager", "System Manager"),
	ACCOUNTING: ("Accounts Manager", "Accounts User", "System Manager"),
}
BUILD_PACKAGE_ROLES = ("Manufacturing Manager", "Projects Manager", "System Manager")
CONFIRMATION_FIELDS = ("function", "confirmed_by", "confirmed_by_name", "confirmed_on", "note")
MTR_DOCUMENT = "Material Test Reports"
NO_WELDING, WORKMANSHIP = "No Welding", "PSIF Workmanship (no code)"
CODE_STANDARDS = ("Required by Design", "Required by Customer")
# Old free-text Welding Code values that mean "no code".
NO_CODE_VALUES = {"", "n/a", "na", "none", "no", "-", "psif", "psif standard", "company standard", "standard"}


def code_required(unit) -> bool:
	return unit.get("welding_standard") in CODE_STANDARDS


def welder_skills(unit) -> tuple[str, ...]:
	"""Skills that qualify a welder for this unit: the code skill for code work; the workmanship
	skill, or the code skill, for PSIF workmanship."""
	stages = frappe.get_all(
		"QC Stage", filters={"weld_record": 1}, fields=["welder_skill", "workmanship_welder_skill"]
	)
	code = [s.welder_skill for s in stages if s.welder_skill]
	if code_required(unit):
		return tuple(dict.fromkeys(code))
	shop = [s.workmanship_welder_skill for s in stages if s.workmanship_welder_skill]
	return tuple(dict.fromkeys(shop + code))


def system_save() -> bool:
	return bool(frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch)


def needs_cross_functional_release(unit) -> bool:
	from hse.shop_qc.doctype.qc_unit.qc_unit import SYSTEM_TYPES

	return bool(
		unit.get("shop")
		and frappe.get_cached_value("Build Shop", unit.shop, "cross_functional_release")
		and unit.get("job_type") != "Repair"
		and unit.get("product_type") in SYSTEM_TYPES
		and not unit.get("installed_in")
	)


# ---------------------------------------------------------------- QC Unit validate
def validate_unit(doc) -> None:
	stamp_build_package(doc)
	set_release_confirmations(doc)
	validate_weld_traceability(doc)
	warn_missing_group_flow(doc)


def stamp_build_package(doc) -> None:
	if not doc.get("build_package_released"):
		doc.build_package_released_by = doc.build_package_released_on = None
		return
	before = None if doc.is_new() else doc.get_doc_before_save()
	newly = not before or not before.get("build_package_released")
	changed = newly or any(
		cstr(doc.get(f)) != cstr(before.get(f))
		for f in ("build_package_drawing_rev", "build_package_bom_rev")
	)
	if not changed:
		return
	if not system_save() and not set(frappe.get_roles()) & set(BUILD_PACKAGE_ROLES):
		frappe.throw(
			_("Only Operations (Manufacturing Manager) can release the build package."),
			title=_("Not Permitted"),
		)
	doc.build_package_drawing_rev = cstr(doc.build_package_drawing_rev).strip() or doc.drawing_rev
	doc.build_package_released_by = frappe.session.user
	doc.build_package_released_on = now_datetime()


def set_release_confirmations(doc) -> None:
	"""Seed one row per function on units that need them, and keep the rows read-only except
	through confirm_release / withdraw_release_confirmation."""
	before = None if doc.is_new() else doc.get_doc_before_save()
	if (
		before
		and before.get("release_confirmations")
		and not doc.flags.release_confirmation_change
		and not system_save()
	):
		old = [
			tuple(cstr(r.get(f)) for f in CONFIRMATION_FIELDS) for r in before.get("release_confirmations")
		]
		new = [tuple(cstr(r.get(f)) for f in CONFIRMATION_FIELDS) for r in doc.get("release_confirmations")]
		if old != new:
			frappe.throw(
				_("Release confirmations are changed with the Confirm Release button only."),
				title=_("Release Confirmations"),
			)
	if needs_cross_functional_release(doc) and not doc.get("release_confirmations"):
		for function in RELEASE_FUNCTIONS:
			doc.append("release_confirmations", {"function": function})


def confirmations_complete(qc_unit: str) -> tuple[bool, list[str], object]:
	"""(complete, functions still to confirm, latest confirmation time)."""
	unit = frappe.db.get_value(
		"QC Unit", qc_unit, ["shop", "job_type", "product_type", "installed_in"], as_dict=True
	)
	if not unit or not needs_cross_functional_release(unit):
		return True, [], None
	rows = frappe.get_all(
		"QC Release Confirmation",
		filters={"parenttype": "QC Unit", "parent": qc_unit},
		fields=["function", "confirmed_on"],
	)
	done = {r.function: r.confirmed_on for r in rows if r.confirmed_on}
	missing = [f for f in RELEASE_FUNCTIONS if f not in done]
	latest = max((get_datetime(v) for v in done.values()), default=None)
	return not missing, missing, latest


@frappe.whitelist(methods=["POST"])
def confirm_release(qc_unit: str, function: str, note: str | None = None) -> dict:
	"""Confirm one function's part of the cross-functional release (QM-400 8.6)."""
	if function not in RELEASE_FUNCTIONS:
		frappe.throw(_("Unknown release function {0}.").format(function))
	frappe.has_permission("QC Unit", "read", qc_unit, throw=True)
	if not set(frappe.get_roles()) & set(CONFIRM_ROLES[function]):
		frappe.throw(_("You cannot confirm release for {0}.").format(_(function)), frappe.PermissionError)
	doc = frappe.get_doc("QC Unit", qc_unit)
	if doc.status in ("Shipped", "Cancelled"):
		frappe.throw(_("QC Unit {0} is {1}.").format(qc_unit, doc.status))
	row = next((r for r in doc.release_confirmations if r.function == function), None)
	if not row:
		row = doc.append("release_confirmations", {"function": function})
	row.update(
		{
			"confirmed_by": frappe.session.user,
			"confirmed_by_name": frappe.utils.get_fullname(frappe.session.user),
			"confirmed_on": now_datetime(),
			"note": cstr(note).strip() or None,
		}
	)
	return save_confirmations(doc, _("{0} confirmed release").format(_(function)))


@frappe.whitelist(methods=["POST"])
def withdraw_release_confirmation(qc_unit: str, function: str, reason: str) -> dict:
	if not cstr(reason).strip():
		frappe.throw(_("Give a reason for withdrawing the confirmation."))
	if function not in RELEASE_FUNCTIONS or not set(frappe.get_roles()) & set(CONFIRM_ROLES[function]):
		frappe.throw(_("You cannot withdraw release for {0}.").format(_(function)), frappe.PermissionError)
	doc = frappe.get_doc("QC Unit", qc_unit)
	if doc.status in ("Shipped", "Cancelled"):
		frappe.throw(_("QC Unit {0} is {1}.").format(qc_unit, doc.status))
	for row in doc.release_confirmations:
		if row.function == function:
			row.update({"confirmed_by": None, "confirmed_by_name": None, "confirmed_on": None, "note": None})
	return save_confirmations(doc, _("{0} withdrew release: {1}").format(_(function), reason))


def save_confirmations(doc, comment: str) -> dict:
	from hse.shop_qc.utils import update_unit_status

	doc.flags.release_confirmation_change = True
	doc.flags.ignore_permissions = True
	doc.save()
	doc.add_comment("Info", comment)
	status = update_unit_status(doc.name)
	return {"status": status}


# ---------------------------------------------------------------- weld traceability
def validate_weld_traceability(doc) -> None:
	doc.weld_performance_code = cstr(doc.get("weld_performance_code")).strip() or None
	if code_required(doc) and not doc.weld_performance_code:
		frappe.throw(
			_("Enter the Welding Code required by {0}.").format(
				_("design") if doc.welding_standard == "Required by Design" else _("the customer")
			),
			title=_("Welding Code Required"),
		)
	if not code_required(doc) and doc.weld_performance_code:
		frappe.throw(
			_(
				"Welding Code {0} is entered, but Welding Standard is {1}. Choose who requires the code, or clear it."
			).format(frappe.bold(doc.weld_performance_code), _(doc.welding_standard or "not set")),
			title=_("Welding Standard"),
		)
	names = {}
	for row in doc.get("welders") or []:
		if row.employee not in names:
			names[row.employee] = frappe.db.get_value("Employee", row.employee, "employee_name")
		row.employee_name = names[row.employee]
		row.skill_authorization, row.qualification_expires = welder_qualification(doc, row.employee)
	if not code_required(doc):
		return
	for row in doc.get("quality_documents") or []:
		if row.document == MTR_DOCUMENT and row.required != "Yes":
			row.required = "Yes"
	names = {}
	for row in doc.get("welders") or []:
		if row.employee not in names:
			names[row.employee] = frappe.db.get_value("Employee", row.employee, "employee_name")
		row.employee_name = names[row.employee]
		row.skill_authorization, row.qualification_expires = welder_qualification(doc, row.employee)
	for row in doc.get("material_traceability") or []:
		row.heat_lot_no = cstr(row.heat_lot_no).strip().upper()


def welder_qualification(doc, employee: str) -> tuple:
	"""The welder's current authorization that fits the unit's welding tier."""
	from hse.shop_qc.doctype.qc_inspection.qc_inspection import active_authorization

	for skill in welder_skills(doc):
		name = active_authorization(employee, skill, getdate())
		if name:
			return name, frappe.db.get_value("Skill Authorization", name, "expires_on")
	return None, None


def warn_missing_group_flow(doc) -> None:
	"""P2: on a multi-group power unit each group needs its own design flow for the test limits."""
	groups = doc.get("pump_motor_groups") or []
	if doc.get("job_type") == "Repair" or len(groups) < 2:
		return
	missing = [g.pmg_tag for g in groups if not g.design_flow_gpm]
	if missing:
		frappe.msgprint(
			_("{0}: no design flow, so the pressure & function test will have no flow limits.").format(
				", ".join(missing)
			),
			indicator="orange",
			alert=True,
		)
