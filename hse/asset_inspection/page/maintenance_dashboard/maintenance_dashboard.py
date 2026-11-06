# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Maintenance Dashboard: the Maintenance pillar page.

Maintenance means every asset category except the Safety Asset Category (HSE Asset Settings,
"Safety Equipment"), unless an inspection template sets its own Purpose (hse.asset_inspection.
purpose). Safety inspections stay on the HSE Dashboard.

Headline strip, items needing attention, maintenance tasks overdue and coming due, open asset
repairs, equipment out of service, open Helpdesk maintenance requests, recent maintenance
inspections, metrics and goals. Everything is filtered by read permission.
"""

from collections import Counter

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate

from hse.asset_inspection import purpose as ap
from hse.hse.page.hse_home.hse_home import (
	PERIODS,
	_assets_out,
	_can,
	_logs_overdue,
	_names_filter,
	_safe,
	att_maint_assets_out,
	att_maint_overdue,
	att_repairs_open,
	att_requests_open,
	latest_reviews,
	metric_groups,
	period_bounds,
)
from hse.quality_metrics.metrics import CLOSED_TICKET, MAINTENANCE_TICKET_FILTER, METRICS, calculate

LOG = "Asset Maintenance Log"
REPAIR = "Asset Repair"
TICKET = "HD Ticket"
DUE_DAYS = 30
LIST_LIMIT = 15

METRIC_GROUPS = [
	(
		"Maintenance",
		[
			"maintenance_on_time_pct",
			"maintenance_overdue",
			"asset_repairs_open",
			"maintenance_requests_open",
		],
	),
	(
		"All equipment (safety and maintenance)",
		["asset_inspection_on_time_pct", "assets_out_of_service"],
	),
]

ATTENTION = [att_maint_assets_out, att_maint_overdue, att_repairs_open, att_requests_open]
LEVEL_ORDER = {"danger": 0, "warning": 1, "info": 2}
LOG_FIELDS = ["asset_name", "item_name", "task_name", "due_date", "maintenance_status", "assign_to_name"]


@frappe.whitelist()
def get_dashboard(period: str = "this_month") -> dict:
	if period not in PERIODS:
		period = "this_month"
	start, end = period_bounds(period)
	return {
		"user": frappe.utils.get_fullname(frappe.session.user),
		"today": str(getdate()),
		"period": {"key": period, "label": _(PERIODS[period]), "start": str(start), "end": str(end)},
		"periods": [{"key": k, "label": _(v)} for k, v in PERIODS.items()],
		"safety_category": ap.safety_category(),
		"headline": _safe(headline) or [],
		"attention": attention(),
		"overdue": _safe(overdue_rows) or [],
		"coming_due": _safe(coming_due_rows) or [],
		"by_category": _safe(overdue_by_category) or [],
		"repairs": _safe(repair_rows, start, end) or [],
		"out_of_service": _safe(out_of_service_rows) or [],
		"requests": _safe(request_rows),
		"inspections": _safe(recent_inspections) or [],
		"metrics": _safe(metric_groups, start, end, METRIC_GROUPS) or [],
		"reviews": _safe(maintenance_reviews) or [],
	}


def attention() -> list[dict]:
	items = [a for a in (_safe(fn) for fn in ATTENTION) if a]
	return sorted(items, key=lambda a: LEVEL_ORDER.get(a["level"], 3))


# --------------------------------------------------------------------------- headline
def _step(key, label, value, tone, doctype, filters=None, detail=None):
	return {
		"key": key,
		"label": label,
		"value": value,
		"tone": tone,
		"doctype": doctype,
		"filters": filters or {},
		"detail": detail,
	}


def headline() -> list[dict]:
	"""Current-state numbers: they do not change with the period."""
	steps = []
	if _can(LOG):
		overdue = _logs_overdue(ap.MAINTENANCE)
		due = _coming_due()
		steps.append(
			_step(
				"maintenance_overdue",
				_("Tasks overdue"),
				len(overdue),
				"bad" if overdue else "",
				LOG,
				_names_filter(overdue),
			)
		)
		steps.append(
			_step(
				"maintenance_due",
				_("Due in {0} days").format(DUE_DAYS),
				len(due),
				"warn" if due else "",
				LOG,
				_names_filter(due),
			)
		)
		pct, detail = calculate("maintenance_on_time_pct", getdate().replace(day=1), getdate())
		steps.append(
			_step(
				"maintenance_on_time_pct",
				_("On time this month"),
				pct,
				"" if pct is None else ("good" if pct >= 95 else "warn" if pct >= 85 else "bad"),
				LOG,
				None,
				detail,
			)
		)
	if _can("Asset"):
		out = _assets_out(None)
		steps.append(
			_step(
				"out_of_service",
				_("Equipment out of service"),
				len(out),
				"bad" if out else "",
				"Asset",
				_names_filter(out),
			)
		)
	if _can(REPAIR):
		f = {"repair_status": "Pending", "docstatus": ["<", 2]}
		n = frappe.db.count(REPAIR, f)
		steps.append(_step("repairs_open", _("Repairs open"), n, "warn" if n else "", REPAIR, f))
	if _can(TICKET) and frappe.db.has_column(TICKET, "ticket_type"):
		f = {**MAINTENANCE_TICKET_FILTER, "status": ["not in", CLOSED_TICKET]}
		n = len(frappe.get_list(TICKET, filters=f, pluck="name", limit_page_length=0))
		steps.append(_step("requests_open", _("Requests open"), n, "warn" if n else "", TICKET, f))
	return steps


# --------------------------------------------------------------------------- lists
def _coming_due(days: int = DUE_DAYS) -> list:
	today = getdate()
	return ap.logs(
		{
			"maintenance_status": ["in", ["Planned", "Overdue"]],
			"due_date": ["between", [str(today), str(add_days(today, days))]],
			"docstatus": ["<", 2],
		},
		ap.MAINTENANCE,
		LOG_FIELDS,
	)


def _log_row(r) -> dict:
	return {
		"doctype": LOG,
		"name": r.name,
		"title": r.asset_name or r.item_name or r.name,
		"subtitle": " · ".join(x for x in (r.task_name, r.assign_to_name) if x),
		"status": r.maintenance_status,
		"date": str(r.due_date) if r.due_date else None,
	}


def overdue_rows() -> list[dict]:
	if not _can(LOG):
		return []
	rows = [r for r in _logs_overdue(ap.MAINTENANCE)]
	if not rows:
		return []
	full = frappe.get_all(
		LOG,
		filters={"name": ["in", [r.name for r in rows]]},
		fields=["name", *LOG_FIELDS],
		order_by="due_date asc",
		limit_page_length=LIST_LIMIT,
	)
	return [_log_row(r) for r in full]


def coming_due_rows() -> list[dict]:
	if not _can(LOG):
		return []
	rows = sorted(_coming_due(), key=lambda r: str(r.due_date))
	return [_log_row(r) for r in rows[:LIST_LIMIT]]


def overdue_by_category() -> list[dict]:
	"""Overdue maintenance tasks per asset category."""
	if not _can(LOG):
		return []
	rows = _logs_overdue(ap.MAINTENANCE)
	if not rows:
		return []
	ams = {r.asset_maintenance for r in rows if r.asset_maintenance}
	cats = dict(
		frappe.get_all(
			"Asset Maintenance",
			filters={"name": ["in", list(ams)]},
			fields=["name", "asset_category"],
			as_list=True,
		)
	)
	by_cat: dict[str, list] = {}
	for r in rows:
		by_cat.setdefault(cats.get(r.asset_maintenance) or _("No category"), []).append(r.name)
	counts = Counter({k: len(v) for k, v in by_cat.items()})
	return [{"label": k, "count": n, "filters": {"name": ["in", by_cat[k]]}} for k, n in counts.most_common()]


def repair_rows(start, end) -> list[dict]:
	"""Open repairs, then repairs completed in the period."""
	if not _can(REPAIR):
		return []
	fields = ["name", "asset", "asset_name", "repair_status", "failure_date", "completion_date"]
	meta = frappe.get_meta(REPAIR)
	fields = [f for f in fields if f == "name" or meta.has_field(f)]
	open_rows = frappe.get_list(
		REPAIR,
		filters={"repair_status": "Pending", "docstatus": ["<", 2]},
		fields=fields,
		order_by="failure_date asc",
		limit_page_length=LIST_LIMIT,
	)
	done = frappe.get_list(
		REPAIR,
		filters={
			"repair_status": "Completed",
			"completion_date": ["between", [str(start), f"{end} 23:59:59"]],
		},
		fields=fields,
		order_by="completion_date desc",
		limit_page_length=LIST_LIMIT,
	)
	out = []
	for r in open_rows + done:
		when = r.get("completion_date") if r.repair_status == "Completed" else r.get("failure_date")
		out.append(
			{
				"doctype": REPAIR,
				"name": r.name,
				"title": r.get("asset_name") or r.get("asset") or r.name,
				"subtitle": r.name,
				"status": r.repair_status,
				"date": str(getdate(when)) if when else None,
			}
		)
	return out


def out_of_service_rows() -> list[dict]:
	"""All equipment out of service, marked Safety or Maintenance."""
	if not _can("Asset"):
		return []
	rows = ap.assets({"safety_status": "Out of Service", "docstatus": 1}, None, ["asset_name", "location"])
	purposes = ap.asset_purposes(rows)
	return [
		{
			"doctype": "Asset",
			"name": r.name,
			"title": r.asset_name or r.name,
			"subtitle": " · ".join(x for x in (r.asset_category, r.location) if x),
			"status": _(purposes.get(r.name)),
			"date": None,
		}
		for r in rows[:LIST_LIMIT]
	]


def request_rows() -> dict | None:
	"""Open Helpdesk tickets whose type contains "Maintenance". None if Helpdesk is not installed."""
	if not (_can(TICKET) and frappe.db.has_column(TICKET, "ticket_type")):
		return None
	f = {**MAINTENANCE_TICKET_FILTER, "status": ["not in", CLOSED_TICKET]}
	rows = frappe.get_list(
		TICKET,
		filters=f,
		fields=["name", "subject", "ticket_type", "status", "priority", "opening_date"],
		order_by="opening_date asc, creation asc",
		limit_page_length=LIST_LIMIT,
	)
	return {
		"filters": f,
		"rows": [
			{
				"doctype": TICKET,
				"name": str(r.name),
				"title": r.subject or str(r.name),
				"subtitle": " · ".join(x for x in (f"#{r.name}", r.ticket_type, r.priority) if x),
				"status": r.status,
				"date": str(r.opening_date) if r.opening_date else None,
				"url": f"/helpdesk/tickets/{r.name}",
			}
			for r in rows
		],
	}


def recent_inspections() -> list[dict]:
	"""Latest maintenance-purpose asset inspections."""
	dt = "Asset Inspection"
	if not _can(dt):
		return []
	rows = frappe.get_list(
		dt,
		filters={"docstatus": ["!=", 2]},
		fields=[
			"name",
			"asset",
			"asset_name",
			"asset_category",
			"template",
			"status",
			"docstatus",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=60,
	)
	overrides = ap.template_purposes()
	out = []
	for r in rows:
		if ap.purpose_of(r.asset_category, r.template, overrides) != ap.MAINTENANCE:
			continue
		out.append(
			{
				"doctype": dt,
				"name": r.name,
				"title": r.asset_name or r.asset or r.name,
				"subtitle": r.template,
				"status": r.status or ("Draft" if r.docstatus == 0 else None),
				"date": str(getdate(r.modified)),
			}
		)
		if len(out) >= 10:
			break
	return out


def maintenance_reviews() -> list[dict]:
	keys = [k for _g, ks in METRIC_GROUPS for k in ks if k in METRICS]
	if not frappe.db.has_column("Quality Goal Objective", "hse_metric"):
		return []
	goals = set(
		frappe.get_all(
			"Quality Goal Objective",
			filters={"parenttype": "Quality Goal", "hse_metric": ["in", keys]},
			pluck="parent",
		)
	)
	return [r for r in latest_reviews() if r["goal"] in goals]


# --------------------------------------------------------------------------- Executive pillar
def pillar() -> dict | None:
	"""Summary and attention for the Executive Dashboard Maintenance card."""
	if not (_can(LOG) or _can("Asset")):
		return None
	steps = {s["key"]: s["value"] for s in headline()}
	return {
		"summary": {
			"maintenance_overdue": cint(steps.get("maintenance_overdue")),
			"maintenance_due": cint(steps.get("maintenance_due")),
			"maintenance_on_time_pct": steps.get("maintenance_on_time_pct"),
			"out_of_service": cint(steps.get("out_of_service")),
			"repairs_open": cint(steps.get("repairs_open")),
			"requests_open": steps.get("requests_open"),
		},
		"attention": attention(),
	}
