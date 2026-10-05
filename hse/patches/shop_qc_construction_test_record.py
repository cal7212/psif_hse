# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""PSIF System Construction Test Record: add the HPU Coating and Pre-Test Preparation stages,
turn on the proof test and coating record flags, refresh the unused sample templates and merge
the new checklist items into the HPU templates. Safe to re-run."""

import json
from pathlib import Path

import frappe

from hse.shop_qc.install import (
	COATING_STAGES,
	DEFAULT_STAGES,
	PROOF_TEST_STAGES,
	create_sample_templates,
)

NEW_HPU_STAGES = ("Coating", "Pre-Test Preparation")
# Replaced by the per-PMG test (rotation, amps) and the drained-for-shipment check.
SUPERSEDED = {
	"HPU - Pressure & Function Test": ("Motor rotation", "No-load current (A)", "Full-load current (A)"),
	"HPU - Final Release": ("Fluid level",),
}
ROW_FIELDS = (
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
	"tolerance_minus_pct",
	"tolerance_plus_pct",
)


def execute():
	if frappe.db.exists("Build Shop", "HPU"):
		for name, seq, req, hold, final, hose in DEFAULT_STAGES[("HPU", "New Build")]:
			if name in NEW_HPU_STAGES and not frappe.db.exists("QC Stage", name):
				frappe.get_doc(
					{
						"doctype": "QC Stage",
						"stage_name": name,
						"sequence": seq,
						"shop": "HPU",
						"job_type": "New Build",
						"is_required": req,
						"hold_point": hold,
						"is_final_release": final,
						"hose_test": hose,
						"coating_record": 1 if name in COATING_STAGES else 0,
					}
				).insert(ignore_permissions=True)
	for flag, stages in (("proof_test", PROOF_TEST_STAGES), ("coating_record", COATING_STAGES)):
		for stage in stages:
			if frappe.db.exists("QC Stage", stage):
				frappe.db.set_value("QC Stage", stage, flag, 1, update_modified=False)
	create_sample_templates(update_unused=True)
	merge_hpu_templates()


def merge_hpu_templates():
	"""Add the new sample items to HPU templates that are in use or edited. Existing rows keep
	their wording and settings; rows the user added stay, after the sample rows. Submitted
	inspections hold their own copy of the checklist and are not changed."""
	data = json.loads((Path(frappe.get_app_path("hse", "shop_qc")) / "sample_templates.json").read_text())
	for sample in data:
		name = sample["template_name"]
		if not name.startswith("HPU - ") or not frappe.db.exists("QC Inspection Template", name):
			continue
		doc = frappe.get_doc("QC Inspection Template", name)
		drop = set(SUPERSEDED.get(name, ()))
		existing = {r.check_item: r for r in doc.items if r.check_item not in drop}
		rows, used = [], set()
		for item in sample["items"]:
			row = existing.get(item["check_item"])
			rows.append({f: row.get(f) for f in ROW_FIELDS} if row else item)
			used.add(item["check_item"])
		rows += [{f: r.get(f) for f in ROW_FIELDS} for r in doc.items if r.check_item not in used | drop]
		if [r["check_item"] for r in rows] == [r.check_item for r in doc.items]:
			continue
		doc.set("items", rows)
		doc.flags.ignore_permissions = True
		doc.save()
