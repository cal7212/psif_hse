# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""QM-400 Rev 3 alignment: switch on the new controls for existing shops, stages and records.

1. Cross-Functional Release on build shops that are not repair or hose shops (8.6).
2. Requires Build Package Release on the new-build stages of those shops (8.5.1); units already
   past Pending Build are marked released at their current Drawing / Rev, as they are on the
   floor already.
3. Weld Traceability Record on stages named Frame & Weld (4.2.1, 7.2, 8.5.2).
4. Welding Standard from the old free-text Welding Code: "n/a"-style values become PSIF
   Workmanship (no code) and the code is cleared; any other value becomes Required by Design,
   with a comment asking someone to confirm design vs customer. Blank stays blank and is asked
   for at the weld stage.
5. Calibration History rows from each instrument's Last Calibrated / certificate (7.1.5).
   Certificates kept on the shared drive need no re-upload: give the row's Certificate
   Location instead.
6. Target Close Date on open NCRs (Appendix C).
7. In-use sample templates: "Welding to code" becomes "Welding to specified standard", showing
   the unit's Welding Standard; unstarted drafts on them are rebuilt.
Direct updates are used for flags and backfills so old records are not re-validated.
"""

import json
from pathlib import Path

import frappe
from frappe.utils import add_days, add_months, cint, cstr, now_datetime

from hse.patches.shop_qc_unit_values_on_checklists import rebuild_unstarted_drafts
from hse.quality_metrics.ncr import DEFAULT_DUE_DAYS, DUE_DAYS
from hse.shop_qc.release import CODE_STANDARDS, NO_CODE_VALUES, WORKMANSHIP

OLD_WELD_LINE, NEW_WELD_LINE = "Welding to code", "Welding to specified standard"


def execute():
	shops = build_shops()
	for shop in shops:
		frappe.db.set_value("Build Shop", shop, "cross_functional_release", 1, update_modified=False)
	stages = frappe.get_all(
		"QC Stage",
		filters={"shop": ("in", shops or [""]), "job_type": ("in", ["New Build", "Both"]), "disabled": 0},
		pluck="name",
	)
	for stage in stages:
		frappe.db.set_value("QC Stage", stage, "requires_build_package", 1, update_modified=False)
	for stage in frappe.get_all("QC Stage", filters={"stage_name": ("like", "%Frame & Weld%")}, pluck="name"):
		frappe.db.set_value("QC Stage", stage, "weld_record", 1, update_modified=False)
	released = backfill_build_packages()
	coded, plain = map_welding_codes()
	calibrations = backfill_calibrations()
	ncrs = backfill_ncr_due_dates()
	templates = update_weld_lines()
	rebuilt = rebuild_unstarted_drafts(templates)
	frappe.clear_cache(doctype="QC Stage")
	print(
		f"QM-400: cross-functional release on {len(shops)} shop(s); build package gate on "
		f"{len(stages)} stage(s); {released} unit(s) marked build package released; welding "
		f"standard set on {coded} coded and {plain} workmanship unit(s); {calibrations} calibration "
		f"history row(s); {ncrs} NCR target date(s); {len(templates)} template(s) and {rebuilt} "
		"draft(s) updated."
	)


def build_shops() -> list[str]:
	hose_shops = set(frappe.get_all("QC Stage", filters={"hose_test": 1}, pluck="shop"))
	return [
		s
		for s in frappe.get_all("Build Shop", filters={"is_repair_shop": 0, "disabled": 0}, pluck="name")
		if s not in hose_shops
	]


def backfill_build_packages() -> int:
	units = frappe.get_all(
		"QC Unit",
		filters={
			"status": ("not in", ["Pending Build", "Cancelled"]),
			"job_type": ("!=", "Repair"),
			"build_package_released": 0,
		},
		fields=["name", "drawing_rev"],
	)
	for u in units:
		frappe.db.set_value(
			"QC Unit",
			u.name,
			{
				"build_package_released": 1,
				"build_package_drawing_rev": u.drawing_rev,
				"build_package_released_by": "Administrator",
				"build_package_released_on": now_datetime(),
			},
			update_modified=False,
		)
	return len(units)


def map_welding_codes() -> tuple[int, int]:
	coded = plain = 0
	for u in frappe.get_all(
		"QC Unit",
		filters={"weld_performance_code": ("is", "set"), "welding_standard": ("in", ["", None])},
		fields=["name", "weld_performance_code"],
	):
		value = cstr(u.weld_performance_code).strip()
		if value.lower() in NO_CODE_VALUES:
			frappe.db.set_value(
				"QC Unit",
				u.name,
				{"welding_standard": WORKMANSHIP, "weld_performance_code": None},
				update_modified=False,
			)
			plain += 1
			continue
		frappe.db.set_value("QC Unit", u.name, "welding_standard", CODE_STANDARDS[0], update_modified=False)
		frappe.get_doc("QC Unit", u.name).add_comment(
			"Info",
			f"Welding Standard set to {CODE_STANDARDS[0]} from Welding Code '{value}' by the QM-400 "
			"update. Change it to Required by Customer if the customer invoked the code.",
		)
		coded += 1
	return coded, plain


def backfill_calibrations() -> int:
	count = 0
	for m in frappe.get_all(
		"Measuring Instrument",
		filters={"calibration_required": 1, "last_calibrated": ("is", "set")},
		fields=[
			"name",
			"last_calibrated",
			"calibrated_by",
			"calibration_certificate",
			"calibration_interval_months",
		],
	):
		if frappe.db.exists("Measuring Instrument Calibration", {"parent": m.name}):
			continue
		row = frappe.get_doc(
			{
				"doctype": "Measuring Instrument Calibration",
				"parenttype": "Measuring Instrument",
				"parentfield": "calibrations",
				"parent": m.name,
				"idx": 1,
				"calibration_date": m.last_calibrated,
				"as_found": "Not Recorded",
				"as_left": "In Tolerance",
				"calibrated_by": m.calibrated_by,
				"certificate": m.calibration_certificate,
				"next_due": add_months(m.last_calibrated, cint(m.calibration_interval_months))
				if cint(m.calibration_interval_months)
				else None,
				"notes": "Carried over from the instrument record by the QM-400 update.",
			}
		)
		row.db_insert()
		count += 1
	return count


def backfill_ncr_due_dates() -> int:
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={
			"status": "Open",
			"record_type": ("!=", "Rework"),
			"ncr_due_date": ("is", "not set"),
			"ncr_date": ("is", "set"),
		},
		fields=["name", "ncr_date", "severity"],
	)
	for r in rows:
		frappe.db.set_value(
			"Nonconformance Report",
			r.name,
			"ncr_due_date",
			add_days(r.ncr_date, DUE_DAYS.get(r.severity, DEFAULT_DUE_DAYS)),
			update_modified=False,
		)
	return len(rows)


def update_weld_lines() -> list[str]:
	samples = json.loads((Path(frappe.get_app_path("hse")) / "shop_qc" / "sample_templates.json").read_text())
	wanted = {
		(t["template_name"], i["check_item"]): i
		for t in samples
		for i in t["items"]
		if i["check_item"] == NEW_WELD_LINE or i.get("unit_text_field") == "welding_standard"
	}
	changed = []
	for name in frappe.get_all(
		"QC Inspection Template Item", filters={"check_item": OLD_WELD_LINE}, pluck="parent", distinct=True
	):
		new = wanted.get((name, NEW_WELD_LINE))
		doc = frappe.get_doc("QC Inspection Template", name)
		for row in doc.items:
			if row.check_item != OLD_WELD_LINE:
				continue
			row.check_item = NEW_WELD_LINE
			row.unit_text_field = "welding_standard"
			if new:
				row.criteria = new["criteria"]
		doc.flags.change_summary = (
			"QM-400 welding: 'Welding to code' became 'Welding to specified standard', showing the "
			"unit's code or the PSIF Welding Workmanship Standard."
		)
		doc.save(ignore_permissions=True)
		changed.append(name)
	return changed
