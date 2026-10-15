# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Required QC per unit: which stages a unit needs, and draft inspections for them.

A unit with Required QC rows uses only its ticked stages (all required); a unit without
rows (created before this table existed) uses every applicable stage as before.
"""

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from hse.shop_qc.utils import STAGE_FIELDS, get_default_template, stage_applies


def applicable_stage_rows(shop: str | None, job_type: str | None) -> list[dict]:
	stages = frappe.get_all(
		"QC Stage", filters={"disabled": 0}, fields=STAGE_FIELDS, order_by="sequence asc, name asc"
	)
	return [
		{"stage": s.name, "sequence": s.sequence, "required": 1}
		for s in stages
		if stage_applies(s, shop, job_type)
	]


def set_qc_stages(doc) -> None:
	"""New units start with every applicable stage ticked; rows must suit the unit's shop."""
	if doc.is_new() and not doc.get("qc_stages") and doc.shop and not frappe.flags.skip_required_qc:
		doc.set("qc_stages", applicable_stage_rows(doc.shop, doc.job_type))
	seen = set()
	for row in doc.get("qc_stages"):
		if row.stage in seen:
			frappe.throw(_("Required QC row {0}: stage {1} is listed twice.").format(row.idx, row.stage))
		seen.add(row.stage)
		stage = frappe.get_cached_doc("QC Stage", row.stage)
		if not stage_applies(stage, doc.shop, doc.job_type):
			frappe.throw(
				_(
					"Required QC row {0}: stage {1} does not apply to {2} {3} units. Clear the Required QC table and use Load QC Stages."
				).format(row.idx, row.stage, doc.shop or "", (doc.job_type or "").lower())
			)
		row.sequence = stage.sequence
		if stage.is_final_release:
			row.required = 1


def get_unit_stage_selection(qc_unit: str | None) -> set | None:
	"""Ticked stages of the unit, or None when the unit has no Required QC rows."""
	if not qc_unit:
		return None
	rows = frappe.get_all(
		"QC Unit Stage",
		filters={"parent": qc_unit, "parenttype": "QC Unit", "parentfield": "qc_stages"},
		fields=["stage", "required"],
	)
	if not rows:
		return None
	return {r.stage for r in rows if cint(r.required)}


def create_draft_inspections(unit) -> list[str]:
	"""A draft QC Inspection for each ticked stage that has none yet (drafts or submitted)."""
	existing = set(
		frappe.get_all("QC Inspection", filters={"qc_unit": unit.name, "docstatus": ("<", 2)}, pluck="stage")
	)
	created, skipped = [], []
	for row in unit.get("qc_stages"):
		if not cint(row.required) or row.stage in existing:
			continue
		template = get_default_template(row.stage, unit.model, unit.product_type)
		if not template:
			skipped.append(_("{0} (no inspection template)").format(row.stage))
			continue
		frappe.db.savepoint("qc_draft_inspection")
		try:
			insp = frappe.get_doc(
				{
					"doctype": "QC Inspection",
					"qc_unit": unit.name,
					"stage": row.stage,
					"template": template,
					"inspection_date": now_datetime(),
				}
			).insert()
		except Exception:
			frappe.db.rollback(save_point="qc_draft_inspection")
			frappe.log_error(title=f"QC draft inspection: {unit.name} {row.stage}")
			skipped.append(_("{0} (could not be created, see Error Log)").format(row.stage))
			continue
		frappe.db.set_value("QC Unit Stage", row.name, "inspection", insp.name, update_modified=False)
		row.inspection = insp.name
		created.append(insp.name)
	if created:
		frappe.msgprint(
			_("Draft inspections created: {0}").format(", ".join(created)), indicator="green", alert=True
		)
	if skipped:
		frappe.msgprint(_("No draft inspection for: {0}").format(", ".join(skipped)), indicator="orange")
	return created


@frappe.whitelist(methods=["POST"])
def make_draft_inspections(qc_unit: str) -> list[str]:
	frappe.has_permission("QC Inspection", "create", throw=True)
	unit = frappe.get_doc("QC Unit", qc_unit)
	unit.check_permission("read")
	if not unit.get("qc_stages"):
		frappe.throw(_("Fill the Required QC table first (Load QC Stages)."))
	created = create_draft_inspections(unit)
	if not created:
		frappe.msgprint(_("Every ticked stage already has an inspection."))
	return created


@frappe.whitelist()
def get_qc_stage_rows(shop: str, job_type: str | None = None) -> list[dict]:
	frappe.has_permission("QC Unit", "read", throw=True)
	return applicable_stage_rows(shop, job_type)
