# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""HSE Dashboard: the Safety pillar page, the counterpart of Shop QC Home.

Safety headline strip, items needing attention, incidents in the period, recent safety
records, safety metrics and goals. Everything is filtered by read permission."""

import frappe
from frappe import _
from frappe.utils import getdate

from hse.hse.page.hse_home.hse_home import (
	PERIODS,
	_can,
	_count,
	_item,
	_safe,
	att_assets_out,
	att_calibration,
	att_hk_due,
	att_hk_overdue,
	att_injury_open,
	att_maintenance_late,
	att_sds_review,
	att_training_overdue,
	att_training_requests,
	latest_reviews,
	metric_groups,
	overdue_range,
	period_bounds,
)
from hse.quality_metrics.metrics import INJURY, INJURY_OPEN, METRICS, calculate

METRIC_GROUPS = [
	(
		"Incidents",
		[
			"incidents_reported",
			"recordable_cases",
			"days_away_cases",
			"near_miss_reports",
			"incidents_open",
			"incident_actions_overdue",
			"incident_actions_on_time_pct",
		],
	),
	(
		"Equipment and housekeeping",
		["asset_inspection_on_time_pct", "assets_out_of_service", "hk_avg_score", "hk_areas_overdue"],
	),
	(
		"Training",
		[
			"training_compliance_pct",
			"training_overdue",
			"training_high_hazard_overdue",
			"training_onboarding_on_time_pct",
		],
	),
]


def att_actions_overdue():
	if not _can(INJURY):
		return None
	f = {"docstatus": ["!=", 2], "date_due": ["between", overdue_range()], "date_done": ["is", "not set"]}
	return _item("actions", _("Incident corrective actions overdue"), _count(INJURY, f), INJURY, f, "danger")


ATTENTION = [
	att_actions_overdue,
	att_assets_out,
	att_injury_open,
	att_hk_overdue,
	att_maintenance_late,
	att_training_overdue,
	att_calibration,
	att_hk_due,
	att_training_requests,
	att_sds_review,
]

LEVEL_ORDER = {"danger": 0, "warning": 1, "info": 2}

RECENT = {
	INJURY: ("incident_date", ["type_of_incident"]),
	"Asset Inspection": ("modified", ["asset_name", "template"]),
	"Housekeeping Inspection": ("modified", ["housekeeping_area", "template"]),
}


@frappe.whitelist()
def get_dashboard(period: str = "this_month") -> dict:
	if period not in PERIODS:
		period = "this_month"
	start, end = period_bounds(period)
	attention = [a for a in (_safe(fn) for fn in ATTENTION) if a]
	attention.sort(key=lambda a: LEVEL_ORDER.get(a["level"], 3))
	return {
		"user": frappe.utils.get_fullname(frappe.session.user),
		"today": str(getdate()),
		"overdue_range": overdue_range(),
		"period": {"key": period, "label": _(PERIODS[period]), "start": str(start), "end": str(end)},
		"periods": [{"key": k, "label": _(v)} for k, v in PERIODS.items()],
		"headline": _safe(headline) or [],
		"attention": attention,
		"incidents": _safe(incident_breakdown, start, end),
		"recent": _safe(recent_records) or [],
		"my_drafts": _safe(my_drafts) or [],
		"metrics": _safe(metric_groups, start, end, METRIC_GROUPS) or [],
		"reviews": _safe(latest_reviews, safety_goals()) or [],
	}


# --------------------------------------------------------------------------- headline strip
def _metric_step(key, label, tone_fn, doctype, filters=None):
	if key not in METRICS or not _can(METRICS[key][4]):
		return None
	value, detail = calculate(key, None, None)
	return {
		"key": key,
		"label": label,
		"value": value,
		"detail": detail,
		"tone": tone_fn(value),
		"doctype": doctype,
		"filters": filters or {},
	}


def headline() -> list[dict]:
	"""Current-state numbers: they do not change with the period."""
	steps = [
		_metric_step(
			"days_since_recordable",
			_("Days since last recordable"),
			lambda v: "good" if v is None or v >= 30 else "warn",
			INJURY,
			{"is_recordable": 1},
		),
		_metric_step(
			"incidents_open",
			_("Open incident reports"),
			lambda v: "warn" if v else "",
			INJURY,
			{"status": ["in", list(INJURY_OPEN)]},
		),
		_metric_step(
			"incident_actions_overdue",
			_("Corrective actions overdue"),
			lambda v: "bad" if v else "",
			INJURY,
			{"date_due": ["between", overdue_range()], "date_done": ["is", "not set"]},
		),
		_metric_step(
			"assets_out_of_service",
			_("Assets out of service"),
			lambda v: "bad" if v else "",
			"Asset",
			{"safety_status": "Out of Service", "docstatus": 1},
		),
		_metric_step(
			"hk_areas_overdue",
			_("Housekeeping areas overdue"),
			lambda v: "warn" if v else "",
			"Housekeeping Area",
		),
		_metric_step(
			"training_compliance_pct",
			_("Training compliance"),
			lambda v: "" if v is None else ("good" if v >= 95 else "warn" if v >= 85 else "bad"),
			"Employee Training Matrix",
		),
	]
	return [s for s in steps if s]


# --------------------------------------------------------------------------- incidents in period
INCIDENT_KINDS = [
	("recordable", "Recordable", {"is_recordable": 1}),
	("first_aid", "First aid only", {"first_aid_only": 1}),
	("near_miss", "Near miss", {"near_miss": 1}),
	("observation", "Safety observation", {"observation": 1}),
]


def incident_breakdown(start, end) -> dict | None:
	if not _can(INJURY):
		return None
	base = {"docstatus": ["!=", 2], "incident_date": ["between", [str(start), str(end)]]}
	total = _count(INJURY, base)
	kinds = []
	for key, label, extra in INCIDENT_KINDS:
		f = {**base, **extra}
		kinds.append({"key": key, "label": _(label), "count": _count(INJURY, f), "filters": f})
	causes = frappe.get_list(
		INJURY,
		filters={**base, "injury_cause": ["is", "set"]},
		fields=["injury_cause", "count(name) as n"],
		group_by="injury_cause",
		order_by="n desc",
		limit_page_length=5,
	)
	return {
		"total": total,
		"filters": base,
		"kinds": kinds,
		"causes": [{"label": c.injury_cause, "count": c.n} for c in causes],
	}


# --------------------------------------------------------------------------- lists
def recent_records() -> list[dict]:
	out = []
	for dt, (date_field, fields) in RECENT.items():
		if not _can(dt):
			continue
		meta = frappe.get_meta(dt)
		keep = [f for f in fields if meta.has_field(f)]
		extra = ["status"] if meta.has_field("status") else []
		if date_field != "modified" and not meta.has_field(date_field):
			date_field = "modified"
		for r in frappe.get_list(
			dt,
			filters={"docstatus": ["!=", 2]},
			fields=["name", "docstatus", "modified", f"{date_field} as on_date", *keep, *extra],
			order_by=f"{date_field} desc, modified desc",
			limit_page_length=5,
		):
			out.append(
				{
					"doctype": dt,
					"name": r.name,
					"title": (r.get(keep[0]) if keep else None) or r.name,
					"subtitle": r.get(keep[1]) if len(keep) > 1 else None,
					"status": r.get("status") or ("Draft" if r.docstatus == 0 else None),
					"date": str(getdate(r.on_date)) if r.on_date else None,
				}
			)
	out.sort(key=lambda r: r["date"] or "", reverse=True)
	return out[:10]


def my_drafts() -> list[dict]:
	out = []
	for dt in RECENT:
		if not _can(dt):
			continue
		for r in frappe.get_list(
			dt,
			filters={"docstatus": 0, "owner": frappe.session.user},
			fields=["name", "modified"],
			order_by="modified desc",
			limit_page_length=4,
		):
			out.append({"doctype": dt, "name": r.name, "modified": str(r.modified)})
	out.sort(key=lambda r: r["modified"], reverse=True)
	return out[:6]


def safety_goals() -> list[str]:
	keys = [k for _g, ks in METRIC_GROUPS for k in ks if k in METRICS]
	if not frappe.db.has_column("Quality Goal Objective", "hse_metric"):
		return []
	return sorted(
		set(
			frappe.get_all(
				"Quality Goal Objective",
				filters={"parenttype": "Quality Goal", "hse_metric": ["in", keys]},
				pluck="parent",
			)
		)
	)
