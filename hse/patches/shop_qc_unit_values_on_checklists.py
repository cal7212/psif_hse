# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Checklist lines stop asking for values the QC Unit already holds.

1. Sample templates nobody has used or edited get the current sample items.
2. Sample templates already in use get only these targeted changes, leaving any other edits:
   - lines that show a unit value get Show Unit Value / Pre-fill Recorded Value as in
     sample_templates.json (only where the line is still unset);
   - the HPU Pressure & Function Test loses the relief, flow, temperature-rise and sound-level
     readings, which the Pump / Motor Group tests now record and judge (only where that
     template's stage loads the PMG tests).
3. Draft inspections on those templates that nobody has started are rebuilt, so they pick up
   the new lines and the PMG test limits. Started drafts keep their lines; Reload Checklist on
   the form rebuilds one by hand."""

import json
from pathlib import Path

import frappe
from frappe.utils import cstr, flt

from hse.shop_qc.install import create_sample_templates

MOVED_TO_PMG_TESTS = {
	"HPU - Pressure & Function Test": (
		"Relief valve setting (psi)",
		"Flow at test pressure (gpm)",
		"Fluid temperature rise (deg F)",
		"Sound level at 1 m (dBA)",
	),
}
ITEM_INPUTS = ("result", "reading_value", "text_value", "finding", "photo")
PMG_INPUTS = (
	"nameplate_verified",
	"rotation_verified",
	"relief_as_set",
	"compensator_as_set",
	"motor_amps",
	"actual_flow_gpm",
	"case_flow_gpm",
	"fluid_temp_begin_f",
	"fluid_temp_end_f",
	"sound_level_db",
	"result",
	"finding",
)


def execute():
	create_sample_templates(update_unused=True)
	samples = json.loads((Path(frappe.get_app_path("hse")) / "shop_qc" / "sample_templates.json").read_text())
	changed = []
	for sample in samples:
		name = sample["template_name"]
		if frappe.db.exists("QC Inspection Template", name) and update_template(name, sample):
			changed.append(name)
	rebuilt = rebuild_unstarted_drafts(changed)
	if changed:
		print(f"Updated in-use checklist templates: {', '.join(changed)}")
	if rebuilt:
		print(f"Rebuilt {rebuilt} unstarted draft inspection(s).")


def update_template(name: str, sample: dict) -> bool:
	doc = frappe.get_doc("QC Inspection Template", name)
	dirty = False
	unit_values = {i["check_item"]: i for i in sample["items"] if i.get("unit_text_field")}
	for row in doc.items:
		want = unit_values.get(row.check_item)
		if want and not row.numeric and not row.unit_text_field:
			row.unit_text_field = want["unit_text_field"]
			row.prefill_text_value = want.get("prefill_text_value", 0)
			dirty = True
	moved = MOVED_TO_PMG_TESTS.get(name)
	if moved and doc.stage and frappe.db.get_value("QC Stage", doc.stage, "pmg_test"):
		keep = [r for r in doc.items if r.check_item not in moved]
		if len(keep) != len(doc.items):
			doc.set("items", keep)
			dirty = True
	if dirty:
		doc.save(ignore_permissions=True)
	return dirty


def untouched(rows, fields) -> bool:
	return not any(
		flt(r.get(f)) if f == "reading_value" else cstr(r.get(f)).strip() for r in rows for f in fields
	)


def rebuild_unstarted_drafts(templates: list[str]) -> int:
	if not templates:
		return 0
	count = 0
	for name in frappe.get_all(
		"QC Inspection", {"docstatus": 0, "template": ("in", templates)}, pluck="name"
	):
		doc = frappe.get_doc("QC Inspection", name)
		if not untouched(doc.items, ITEM_INPUTS):
			continue
		doc.set("items", [])  # validate() reloads them from the template
		if doc.pmg_tests and untouched(doc.pmg_tests, PMG_INPUTS):
			doc.set("pmg_tests", [])  # and the PMG rows, now with their test limits
		frappe.db.savepoint("qc_draft_rebuild")
		try:
			doc.save(ignore_permissions=True)
			count += 1
		except frappe.ValidationError:
			# A draft that no longer validates (e.g. its stage was dropped from the unit)
			# is left as it was for someone to look at.
			frappe.db.rollback(save_point="qc_draft_rebuild")
			frappe.clear_messages()
			print(f"Skipped draft inspection {name}: it does not validate as it stands.")
	return count
