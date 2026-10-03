# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""QC status for QC Units, driven by QC Inspections and Non Conformances.

Stages apply to a unit when the stage's shop is the unit's shop (or blank = every shop)
and the stage's job type is the unit's job type (or "Both").
"""

import frappe
from frappe import _
from frappe.utils import cstr

LOCKED_STATUSES = ("Shipped", "Cancelled")  # set by the TrulinX sync; QC does not override
STAGE_FIELDS = [
	"name",
	"sequence",
	"shop",
	"job_type",
	"is_required",
	"hold_point",
	"is_final_release",
	"hose_test",
]


def get_unit_context(qc_unit: str | None) -> frappe._dict:
	if not qc_unit:
		return frappe._dict()
	return frappe._dict(
		frappe.db.get_value("QC Unit", qc_unit, ["shop", "job_type", "product_type", "model"], as_dict=True)
		or {}
	)


def stage_applies(stage, shop: str | None, job_type: str | None) -> bool:
	if stage.shop and stage.shop != shop:
		return False
	return (stage.job_type or "New Build") in (job_type or "New Build", "Both")


def get_stages(qc_unit: str | None = None, required_only: bool = False) -> list[dict]:
	"""Enabled stages in sequence order; limited to the unit's shop and job type when given."""
	filters = {"disabled": 0}
	if required_only:
		filters["is_required"] = 1
	stages = frappe.get_all(
		"QC Stage", filters=filters, fields=STAGE_FIELDS, order_by="sequence asc, name asc"
	)
	if not qc_unit:
		return stages
	ctx = get_unit_context(qc_unit)
	return [s for s in stages if stage_applies(s, ctx.shop, ctx.job_type)]


def get_final_stage(stages: list[dict]):
	return next((s for s in reversed(stages) if s.is_final_release), None)


def get_accepted_by_stage(qc_unit: str) -> dict:
	"""{stage: latest accepted, submitted inspection} for a unit."""
	rows = frappe.get_all(
		"QC Inspection",
		filters={"qc_unit": qc_unit, "docstatus": 1, "status": "Accepted"},
		fields=["name", "stage", "inspection_date", "inspected_by", "inspector_name", "modified_by"],
		order_by="inspection_date asc",
	)
	return {r.stage: r for r in rows}


def count_open_ncs(qc_unit: str) -> int:
	return frappe.db.count("Non Conformance", {"qc_unit": qc_unit, "status": "Open"})


def update_unit_status(qc_unit: str) -> str | None:
	if not qc_unit or not frappe.db.exists("QC Unit", qc_unit):
		return None

	unit = frappe.db.get_value(
		"QC Unit", qc_unit, ["status", "open_non_conformances", "released_on"], as_dict=True
	)
	open_ncs = count_open_ncs(qc_unit)
	values = {"open_non_conformances": open_ncs}

	if unit.status in LOCKED_STATUSES:
		new_status = unit.status
	else:
		stages = get_stages(qc_unit)
		accepted = get_accepted_by_stage(qc_unit)
		final = get_final_stage(stages)
		required_build = [s.name for s in stages if s.is_required and not s.is_final_release]
		has_any = frappe.db.exists("QC Inspection", {"qc_unit": qc_unit, "docstatus": 1})

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
	frappe.db.set_value("QC Unit", qc_unit, values)
	if new_status != unit.status:
		frappe.get_doc("QC Unit", qc_unit).add_comment(
			"Info", _("QC Status changed from {0} to {1}").format(unit.status, new_status)
		)
	return new_status


@frappe.whitelist()
def get_stage_progress(qc_unit: str) -> list[dict]:
	"""One row per applicable stage with the latest inspection outcome, for the QC Unit form."""
	frappe.has_permission("QC Unit", "read", qc_unit, throw=True)
	latest = {}
	for r in frappe.get_all(
		"QC Inspection",
		filters={"qc_unit": qc_unit, "docstatus": ["<", 2]},
		fields=["name", "stage", "status", "docstatus", "inspection_date", "inspector_name"],
		order_by="inspection_date asc",
	):
		prev = latest.get(r.stage)
		# An Accepted record wins over a later draft; otherwise show the most recent.
		if not (prev and prev.status == "Accepted" and prev.docstatus == 1):
			latest[r.stage] = r
	out = []
	for s in get_stages(qc_unit):
		r = latest.get(s.name)
		out.append(
			{
				"stage": s.name,
				"sequence": s.sequence,
				"is_required": s.is_required,
				"is_final_release": s.is_final_release,
				"inspection": r.name if r else None,
				"status": (r.status if r.docstatus == 1 else "Draft") if r else "Not Started",
				"inspection_date": r.inspection_date if r else None,
				"inspector_name": r.inspector_name if r else None,
			}
		)
	return out


@frappe.whitelist()
def get_next_stage(qc_unit: str) -> str | None:
	"""First applicable stage without an Accepted inspection."""
	frappe.has_permission("QC Unit", "read", qc_unit, throw=True)
	accepted = get_accepted_by_stage(qc_unit)
	for s in get_stages(qc_unit):
		if s.name not in accepted:
			return s.name
	return None


@frappe.whitelist()
def get_applicable_stages(qc_unit: str) -> list[str]:
	frappe.has_permission("QC Unit", "read", qc_unit, throw=True)
	return [s.name for s in get_stages(qc_unit)]


def template_matches(t, product_type: str | None, model: str | None) -> bool:
	if t.product_type and t.product_type != product_type:
		return False
	if t.model_prefix and not cstr(model).upper().startswith(t.model_prefix.upper()):
		return False
	return True


@frappe.whitelist()
def get_default_template(stage: str, model: str | None = None, product_type: str | None = None) -> str | None:
	"""Most specific enabled template for the stage: product type and longest model prefix win."""
	templates = frappe.get_all(
		"QC Inspection Template",
		filters={"stage": stage, "disabled": 0},
		fields=["name", "model_prefix", "product_type"],
	)
	matches = [t for t in templates if template_matches(t, product_type, model)]
	if not matches:
		return None

	def rank(t):
		return (1 if t.product_type else 0, len(t.model_prefix or ""))

	best = max(rank(t) for t in matches)
	top = [t for t in matches if rank(t) == best]
	return top[0].name if len(top) == 1 else None


@frappe.whitelist()
def get_certificate_format(qc_unit: str) -> str:
	"""Print format for the unit's QC certificate."""
	frappe.has_permission("QC Unit", "read", qc_unit, throw=True)
	ctx = get_unit_context(qc_unit)
	return certificate_format_for(ctx.job_type, ctx.product_type)


def certificate_format_for(job_type: str | None, product_type: str | None) -> str:
	if job_type == "Repair":
		return "QC Repair Report"
	if product_type == "Hose Assembly":
		return "Hose Assembly Test Certificate"
	if product_type in ("Manifold", "Valve Stand"):
		return "Manifold QC Certificate"
	return "Power Unit QC Certificate"


def get_qc_certificate_data(qc_unit: str) -> frappe._dict:
	"""Jinja helper: everything a QC certificate prints for a unit."""
	unit = frappe.get_doc("QC Unit", qc_unit)
	shop = frappe.get_cached_doc("Build Shop", unit.shop) if unit.shop else frappe._dict()
	stages = get_stages(qc_unit)
	accepted = get_accepted_by_stage(qc_unit)
	inspections = []
	hose_results = {}
	for s in stages:
		acc = accepted.get(s.name)
		if not acc:
			continue
		doc = frappe.get_doc("QC Inspection", acc.name)
		inspections.append(doc)
		for h in doc.hose_tests:
			hose_results[h.hose_tag] = frappe._dict(h.as_dict(), inspection=doc.name, stage=s.name)
	return frappe._dict(
		unit=unit,
		shop=shop,
		title=shop.get("certificate_title") or _("{0} Quality Control Certificate").format(unit.shop or ""),
		statement=shop.get("certificate_statement"),
		stages=stages,
		accepted=accepted,
		inspections=inspections,
		hose_results=hose_results,
		released=unit.status in ("Released", "Shipped"),
		released_by_name=frappe.db.get_value("User", unit.released_by, "full_name")
		if unit.released_by
		else "",
	)
