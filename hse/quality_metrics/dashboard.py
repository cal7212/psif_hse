# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Number Cards and the Quality Metrics workspace.

Every card is a Custom Number Card that calls get_card_value with
filters_json = {"metric": <key in METRICS>, "period": <key in PERIODS>}.
Edit a card's Filters JSON on the site to change its period. Cards and the
workspace are created once on migrate; later edits on the site are kept.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, get_first_day, getdate, today

from hse.quality_metrics.metrics import METRICS, _exists, calculate, get_review_period

CARD_METHOD = "hse.quality_metrics.dashboard.get_card_value"
WORKSPACE = "Quality Metrics"
SIDEBAR = "Quality"
MODULE = "Quality Metrics"

PERIODS = {
	"month_to_date": "Month to date",
	"last_month": "Last month",
	"quarter_to_date": "Quarter to date",
	"last_30_days": "Last 30 days",
	"last_90_days": "Last 90 days",
}

# (card label, metric, period, colour)
CARDS = [
	("QC First-Pass Yield (MTD)", "hpu_first_pass_yield", "month_to_date", "#29CD42"),
	("Shipped Before QC Release (MTD)", "hpu_shipped_before_release", "month_to_date", "#ED6396"),
	("QC Inspections Rejected (MTD)", "hpu_stage_rejections", "month_to_date", "#ECAD4B"),
	("Repair Turnaround Days (90 Days)", "repair_turnaround_days", "last_90_days", "#5E64FF"),
	("Days to Resolve NC (90 Days)", "nc_avg_days_to_resolve", "last_90_days", "#5E64FF"),
	("Critical NCs Open Over 7 Days", "nc_open_critical_over_7_days", "month_to_date", "#ED6396"),
	("Asset Inspections On Time (MTD)", "asset_inspection_on_time_pct", "month_to_date", "#29CD42"),
	("Assets Out of Service", "assets_out_of_service", "month_to_date", "#ED6396"),
	("Housekeeping Avg Score (MTD)", "hk_avg_score", "month_to_date", "#29CD42"),
	("Housekeeping Areas Overdue", "hk_areas_overdue", "month_to_date", "#ECAD4B"),
]

SHORTCUTS = [
	("Quality Goals", "Quality Goal"),
	("Quality Reviews", "Quality Review"),
	("Quality Actions", "Quality Action"),
	("Non Conformances", "Non Conformance"),
]


def get_period(period: str | None, on_date=None):
	ref = getdate(on_date or today())
	if period == "last_month":
		return get_review_period("Monthly", ref)
	if period == "quarter_to_date":
		return getdate(f"{ref.year}-{((ref.month - 1) // 3) * 3 + 1:02d}-01"), ref
	if period == "last_30_days":
		return getdate(add_days(ref, -29)), ref
	if period == "last_90_days":
		return getdate(add_days(ref, -89)), ref
	return getdate(get_first_day(ref)), ref


def _between(start, end):
	return ["between", [str(start), str(end)]]


def get_route(metric: str, start, end) -> tuple[list, dict]:
	"""List view (with filters) a card opens when clicked."""
	period = _between(start, end)
	routes = {
		"hpu_first_pass_yield": ("QC Unit", {"released_on": period}),
		"hpu_units_released": ("QC Unit", {"released_on": period}),
		"hpu_shipped_before_release": ("QC Unit", {"trulinx_ship_date": period, "qc_flag": ["is", "set"]}),
		"hpu_stage_rejections": (
			"QC Inspection",
			{"inspection_date": period, "status": "Rejected", "docstatus": 1},
		),
		"rga_received": ("QC Unit", {"job_type": "Repair"}),
		"repair_turnaround_days": ("QC Unit", {"job_type": "Repair", "released_on": period}),
		"repair_failure_causes": ("QC Unit", {"job_type": "Repair"}),
		"nc_avg_days_to_resolve": ("Non Conformance", {"status": "Resolved", "resolved_on": period}),
		"nc_open_critical_over_7_days": ("Non Conformance", {"status": "Open", "severity": "Critical"}),
		"nc_opened": ("Non Conformance", {"creation": period}),
		"asset_inspection_on_time_pct": ("Asset Maintenance Log", {"due_date": period}),
		"assets_out_of_service": ("Asset", {"safety_status": "Out of Service"}),
		"hk_avg_score": ("Housekeeping Inspection", {"inspection_date": period, "docstatus": 1}),
		"hk_areas_overdue": ("Housekeeping Area", {"schedule_status": "Overdue", "disabled": 0}),
	}
	doctype, options = routes.get(metric, (METRICS[metric][4], {}))
	return ["List", doctype], options


FIELDTYPES = {"Percent": "Percent", "Day": "Float", "Nos": "Int"}


@frappe.whitelist()
def get_card_value(filters: str | dict | None = None) -> dict:
	"""Number Card method. filters: {"metric": ..., "period": ...}."""
	filters = frappe.parse_json(filters) or {}
	metric = filters.get("metric")
	if metric not in METRICS:
		frappe.throw(_("Unknown metric {0}.").format(metric))
	_label, _fn, uom, _snapshot, doctype = METRICS[metric]
	if _exists(doctype) and not frappe.has_permission(doctype, "read"):
		frappe.throw(_("Not permitted to read {0}.").format(_(doctype)), frappe.PermissionError)

	start, end = get_period(filters.get("period"))
	value, _detail = calculate(metric, start, end)
	route, route_options = get_route(metric, start, end)
	return {
		"value": value,
		"fieldtype": FIELDTYPES.get(uom, "Float"),
		"route": route,
		"route_options": route_options,
	}


# ---------------------------------------------------------------- setup
def make_number_cards() -> list[str]:
	created = []
	for label, metric, period, color in CARDS:
		if frappe.db.exists("Number Card", label):
			continue
		card = frappe.get_doc(
			{
				"doctype": "Number Card",
				"name": label,
				"label": label,
				"type": "Custom",
				"method": CARD_METHOD,
				"filters_json": json.dumps({"metric": metric, "period": period}),
				"document_type": METRICS[metric][4],
				"is_public": 1,
				"is_standard": 0,
				"module": MODULE,
				"color": color,
				"show_full_number": 1,
			}
		)
		card.insert(ignore_permissions=True)
		created.append(card.name)
	return created


def _content():
	blocks = [
		{
			"id": "qm_head",
			"type": "header",
			"data": {"text": '<span class="h4"><b>Quality Metrics</b></span>', "col": 12},
		},
	]
	for i, (label, *_rest) in enumerate(CARDS):
		blocks.append(
			{"id": f"qm_card_{i}", "type": "number_card", "data": {"number_card_name": label, "col": 4}}
		)
	blocks += [
		{"id": "qm_spacer", "type": "spacer", "data": {"col": 12}},
		{
			"id": "qm_head2",
			"type": "header",
			"data": {"text": '<span class="h4"><b>Reviews</b></span>', "col": 12},
		},
	]
	for i, (label, _dt) in enumerate(SHORTCUTS):
		blocks.append({"id": f"qm_sc_{i}", "type": "shortcut", "data": {"shortcut_name": label, "col": 3}})
	blocks.append(
		{
			"id": "qm_note",
			"type": "paragraph",
			"data": {
				"text": "MTD = month to date. Cards marked (now) or without a period show the current count. "
				"Click a card to open the records behind it. Monthly pass/fail is recorded in Quality Reviews.",
				"col": 12,
			},
		}
	)
	return json.dumps(blocks)


def make_workspace() -> bool:
	if frappe.db.exists("Workspace", WORKSPACE):
		return False
	ws = frappe.get_doc(
		{
			"doctype": "Workspace",
			"name": WORKSPACE,
			"label": WORKSPACE,
			"title": WORKSPACE,
			"type": "Workspace",
			"module": MODULE,
			"app": "hse",
			"public": 1,
			"icon": "quality",
			"content": _content(),
			"number_cards": [{"number_card_name": label, "label": label} for label, *_rest in CARDS],
			"shortcuts": [
				{"type": "DocType", "link_to": dt, "label": label, "doc_view": "List"}
				for label, dt in SHORTCUTS
			],
		}
	)
	ws.insert(ignore_permissions=True)
	return True


def add_to_quality_sidebar() -> bool:
	"""Add a 'Quality Metrics' link under Home in ERPNext's Quality sidebar (re-added after
	ERPNext resets the sidebar on update)."""
	if not frappe.db.exists("Workspace Sidebar", SIDEBAR):
		return False
	sidebar = frappe.get_doc("Workspace Sidebar", SIDEBAR)
	if any(i.link_type == "Workspace" and i.link_to == WORKSPACE for i in sidebar.items):
		return False
	item = sidebar.append(
		"items",
		{
			"type": "Link",
			"label": WORKSPACE,
			"link_type": "Workspace",
			"link_to": WORKSPACE,
			"icon": "chart-column",
		},
	)
	sidebar.items.remove(item)
	sidebar.items.insert(1 if sidebar.items else 0, item)
	for i, row in enumerate(sidebar.items, 1):
		row.idx = i
	sidebar.save(ignore_permissions=True)
	return True


def setup_dashboard():
	make_number_cards()
	make_workspace()
	try:
		add_to_quality_sidebar()
	except Exception:
		# The sidebar link is a convenience; never fail a migrate over it.
		frappe.log_error(title="Quality Metrics: could not add sidebar link")
