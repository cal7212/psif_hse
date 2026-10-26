# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""One row per QC Unit: QC status, stages accepted, next stage, open NCs and missing parts."""

import frappe
from frappe import _
from frappe.utils import cint

from hse.shop_qc.dashboard import ACTIVE_STATUSES, open_missing_parts, unit_progress

STATUS_ORDER = (
	"QC Hold",
	"In Build",
	"Pending Build",
	"Ready for Release",
	"Released",
	"Shipped",
	"Cancelled",
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, get_chart(data)


def get_columns():
	return [
		{
			"label": _("QC Unit"),
			"fieldname": "qc_unit",
			"fieldtype": "Link",
			"options": "QC Unit",
			"width": 130,
		},
		{"label": _("QC Status"), "fieldname": "status", "fieldtype": "Data", "width": 130},
		{"label": _("Stages Accepted"), "fieldname": "stages", "fieldtype": "Data", "width": 120},
		{"label": _("Progress %"), "fieldname": "progress", "fieldtype": "Percent", "width": 100},
		{
			"label": _("Next Stage"),
			"fieldname": "next_stage",
			"fieldtype": "Link",
			"options": "QC Stage",
			"width": 150,
		},
		{"label": _("Open NCs"), "fieldname": "open_ncs", "fieldtype": "Int", "width": 85},
		{"label": _("Missing Parts"), "fieldname": "missing_parts", "fieldtype": "Int", "width": 105},
		{"label": _("Model"), "fieldname": "model", "fieldtype": "Data", "width": 150},
		{"label": _("Serial No"), "fieldname": "serial_no", "fieldtype": "Data", "width": 120},
		{"label": _("Project"), "fieldname": "project_name", "fieldtype": "Data", "width": 150},
		{"label": _("Customer"), "fieldname": "customer_name", "fieldtype": "Data", "width": 150},
		{"label": _("Shop"), "fieldname": "shop", "fieldtype": "Link", "options": "Build Shop", "width": 110},
		{"label": _("Product Type"), "fieldname": "product_type", "fieldtype": "Data", "width": 110},
		{"label": _("Job Type"), "fieldname": "job_type", "fieldtype": "Data", "width": 90},
		{
			"label": _("Installed In"),
			"fieldname": "installed_in",
			"fieldtype": "Link",
			"options": "QC Unit",
			"width": 120,
		},
		{"label": _("Promised Date"), "fieldname": "promised_date", "fieldtype": "Date", "width": 110},
		{"label": _("Released On"), "fieldname": "released_on", "fieldtype": "Datetime", "width": 150},
	]


def get_filters(filters) -> dict:
	out = {}
	for field in ("shop", "product_type", "job_type"):
		if filters.get(field):
			out[field] = filters.get(field)
	if filters.get("status"):
		out["status"] = filters.status
	elif not cint(filters.get("include_completed")):
		out["status"] = ["in", ACTIVE_STATUSES]
	return out


def get_data(filters) -> list[dict]:
	units = frappe.get_list(
		"QC Unit",
		filters=get_filters(filters),
		fields=[
			"name",
			"status",
			"model",
			"serial_no",
			"project_name",
			"customer_name",
			"shop",
			"product_type",
			"job_type",
			"installed_in",
			"promised_date",
			"released_on",
			"open_non_conformances",
		],
		order_by="name asc",
	)
	missing = open_missing_parts([u.name for u in units])
	rows = []
	for u in units:
		if cint(filters.get("missing_parts")) and not missing.get(u.name):
			continue
		p = unit_progress(u.name)
		rows.append(
			{
				"qc_unit": u.name,
				"status": u.status,
				"stages": f"{p['stages_accepted']} / {p['stages_total']}",
				"progress": p["progress"],
				"next_stage": p["next_stage"],
				"open_ncs": cint(u.open_non_conformances),
				"missing_parts": missing.get(u.name, 0),
				"model": u.model,
				"serial_no": u.serial_no,
				"project_name": u.project_name,
				"customer_name": u.customer_name,
				"shop": u.shop,
				"product_type": u.product_type,
				"job_type": u.job_type,
				"installed_in": u.installed_in,
				"promised_date": u.promised_date,
				"released_on": u.released_on,
			}
		)
	rank = {s: i for i, s in enumerate(STATUS_ORDER)}
	rows.sort(key=lambda r: (rank.get(r["status"], len(rank)), r["qc_unit"]))
	return rows


def get_chart(data):
	if not data:
		return None
	counts = {}
	for r in data:
		counts[r["status"]] = counts.get(r["status"], 0) + 1
	labels = [s for s in STATUS_ORDER if s in counts]
	return {
		"data": {"labels": labels, "datasets": [{"name": _("Units"), "values": [counts[s] for s in labels]}]},
		"type": "bar",
		"height": 220,
	}
