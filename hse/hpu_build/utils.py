# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""QC status for HPU Units, driven by HPU Build Inspections and Non Conformances."""

import frappe
from frappe import _

LOCKED_STATUSES = ("Shipped", "Cancelled")  # set by the TrulinX sync; QC does not override


def get_stages(required_only: bool = False) -> list[dict]:
	filters = {"disabled": 0}
	if required_only:
		filters["is_required"] = 1
	return frappe.get_all(
		"HPU Build Stage",
		filters=filters,
		fields=["name", "sequence", "is_required", "hold_point", "is_final_release"],
		order_by="sequence asc",
	)


def get_accepted_by_stage(hpu_unit: str) -> dict:
	"""{stage: latest accepted, submitted inspection} for a unit."""
	rows = frappe.get_all(
		"HPU Build Inspection",
		filters={"hpu_unit": hpu_unit, "docstatus": 1, "status": "Accepted"},
		fields=["name", "stage", "inspection_date", "inspected_by", "inspector_name", "modified_by"],
		order_by="inspection_date asc",
	)
	return {r.stage: r for r in rows}


def count_open_ncs(hpu_unit: str) -> int:
	return frappe.db.count("Non Conformance", {"hpu_unit": hpu_unit, "status": "Open"})


def update_hpu_unit_status(hpu_unit: str) -> str | None:
	if not hpu_unit or not frappe.db.exists("HPU Unit", hpu_unit):
		return None

	unit = frappe.db.get_value(
		"HPU Unit", hpu_unit, ["status", "open_non_conformances", "released_on"], as_dict=True
	)
	open_ncs = count_open_ncs(hpu_unit)
	values = {"open_non_conformances": open_ncs}

	if unit.status in LOCKED_STATUSES:
		new_status = unit.status
	else:
		stages = get_stages()
		accepted = get_accepted_by_stage(hpu_unit)
		final = next((s for s in stages if s.is_final_release), None)
		required_build = [s.name for s in stages if s.is_required and not s.is_final_release]
		has_any = frappe.db.exists("HPU Build Inspection", {"hpu_unit": hpu_unit, "docstatus": 1})

		if open_ncs:
			new_status = "QC Hold"
		elif final and final.name in accepted:
			new_status = "Released"
		elif required_build and all(s in accepted for s in required_build):
			new_status = "Ready for Release"
		elif has_any:
			new_status = "In Build"
		else:
			new_status = "Pending Build"

		if new_status == "Released":
			rel = accepted[final.name]
			values["released_on"] = rel.inspection_date
			values["released_by"] = rel.modified_by  # user who submitted the release inspection
		elif unit.released_on:
			values["released_on"] = None
			values["released_by"] = None

	values["status"] = new_status
	# db.set_value: no version noise and does not disturb the TrulinX sync hash
	frappe.db.set_value("HPU Unit", hpu_unit, values)
	if new_status != unit.status:
		frappe.get_doc("HPU Unit", hpu_unit).add_comment(
			"Info", _("QC Status changed from {0} to {1}").format(unit.status, new_status)
		)
	return new_status


@frappe.whitelist()
def get_stage_progress(hpu_unit: str) -> list[dict]:
	"""One row per active stage with the latest inspection outcome, for the HPU Unit form."""
	frappe.has_permission("HPU Unit", "read", hpu_unit, throw=True)
	latest = {}
	for r in frappe.get_all(
		"HPU Build Inspection",
		filters={"hpu_unit": hpu_unit, "docstatus": ["<", 2]},
		fields=["name", "stage", "status", "docstatus", "inspection_date", "inspector_name"],
		order_by="inspection_date asc",
	):
		prev = latest.get(r.stage)
		# An Accepted record wins over a later draft; otherwise show the most recent.
		if not (prev and prev.status == "Accepted" and prev.docstatus == 1):
			latest[r.stage] = r
	out = []
	for s in get_stages():
		r = latest.get(s.name)
		out.append({
			"stage": s.name,
			"sequence": s.sequence,
			"is_required": s.is_required,
			"is_final_release": s.is_final_release,
			"inspection": r.name if r else None,
			"status": (r.status if r.docstatus == 1 else "Draft") if r else "Not Started",
			"inspection_date": r.inspection_date if r else None,
			"inspector_name": r.inspector_name if r else None,
		})
	return out


@frappe.whitelist()
def get_next_stage(hpu_unit: str) -> str | None:
	"""First active stage without an Accepted inspection."""
	frappe.has_permission("HPU Unit", "read", hpu_unit, throw=True)
	accepted = get_accepted_by_stage(hpu_unit)
	for s in get_stages():
		if s.name not in accepted:
			return s.name
	return None


@frappe.whitelist()
def get_default_template(stage: str, model: str | None = None) -> str | None:
	"""Most specific enabled template for the stage: longest matching model prefix, then generic."""
	templates = frappe.get_all(
		"HPU Build Inspection Template",
		filters={"stage": stage, "disabled": 0},
		fields=["name", "model_prefix"],
	)
	model = (model or "").upper()
	matches = [t for t in templates if t.model_prefix and model.startswith(t.model_prefix.upper())]
	if matches:
		return max(matches, key=lambda t: len(t.model_prefix)).name
	generic = [t for t in templates if not t.model_prefix]
	return generic[0].name if len(generic) == 1 else None
