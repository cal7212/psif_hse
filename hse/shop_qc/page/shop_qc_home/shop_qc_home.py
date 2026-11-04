# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Shop QC Home: unit pipeline, items needing attention, first-pass yield by stage,
recent inspections, quality metrics and goals. Everything is filtered by read permission."""

import frappe
from frappe import _
from frappe.utils import add_days, getdate

from hse.hse.page.hse_home.hse_home import (
	PERIODS,
	_can,
	_count,
	_item,
	_safe,
	att_calibration,
	att_capa_overdue,
	att_scar_overdue,
	latest_reviews,
	metric_groups,
	overdue_range,
	period_bounds,
)
from hse.quality_metrics.metrics import METRICS, first_inspections, fpy_summary

UNIT = "QC Unit"
INSP = "QC Inspection"
NCR = "Nonconformance Report"
ACTIVE = ["Pending Build", "In Build", "QC Hold", "Ready for Release"]

METRIC_GROUPS = [
	(
		"Build quality",
		[
			"hpu_first_pass_yield",
			"qc_first_pass_yield_by_stage",
			"hpu_units_released",
			"hpu_stage_rejections",
			"hpu_shipped_before_release",
		],
	),
	(
		"Rework",
		[
			"rework_opened",
			"rework_escalation_pct",
			"rework_avg_days_to_close",
			"rework_accept_pct",
			"rework_open_over_7_days",
		],
	),
	(
		"NCR",
		[
			"nc_opened",
			"nc_avg_days_to_resolve",
			"nc_open_over_30_days",
			"nc_open_critical_over_7_days",
			"nc_capa_pct",
		],
	),
	(
		"CAPA",
		[
			"capa_opened",
			"capa_open",
			"capa_overdue",
			"capa_containment_on_time_pct",
			"capa_correction_on_time_pct",
			"capa_closed_on_time_pct",
			"capa_effective_pct",
		],
	),
	("Repairs", ["rga_received", "repair_turnaround_days", "repair_failure_causes"]),
]


@frappe.whitelist()
def get_home(period: str = "this_month", shop: str | None = None) -> dict:
	if period not in PERIODS:
		period = "this_month"
	shops = _safe(shop_list) or []
	if shop not in shops:
		shop = None
	start, end = period_bounds(period)
	return {
		"user": frappe.utils.get_fullname(frappe.session.user),
		"today": str(getdate()),
		"overdue_range": overdue_range(),
		"period": {"key": period, "label": _(PERIODS[period]), "start": str(start), "end": str(end)},
		"periods": [{"key": k, "label": _(v)} for k, v in PERIODS.items()],
		"shop": shop,
		"shops": shops,
		"pipeline": _safe(pipeline, shop, start, end),
		"attention": [a for a in (_safe(fn, shop) for fn in ATTENTION) if a],
		"stage_yield": _safe(stage_yield, shop, start, end),
		"recent": _safe(recent_inspections, shop) or [],
		"my_drafts": _safe(my_drafts) or [],
		"metrics": _safe(metric_groups, start, end, METRIC_GROUPS) or [],
		"reviews": _safe(latest_reviews, qc_goals()) or [],
	}


@frappe.whitelist()
def find_work_order(work_order: str) -> list[str]:
	"""QC Units whose TrulinX work order (or parent / installed-in work order) matches."""
	work_order = (work_order or "").strip()
	if not work_order or not _can(UNIT):
		return []
	names = []
	for field in ("trulinx_work_order", "parent_work_order", "installed_in_work_order"):
		for n in frappe.get_list(
			UNIT, filters={field: ["like", f"%{work_order}%"]}, pluck="name", limit_page_length=50
		):
			if n not in names:
				names.append(n)
	return names


def shop_list() -> list[str]:
	if not _can("Build Shop"):
		return []
	return frappe.get_list("Build Shop", filters={"disabled": 0}, pluck="name", order_by="name asc")


def _unit_filters(shop, **extra):
	f = dict(extra)
	if shop:
		f["shop"] = shop
	return f


# --------------------------------------------------------------------------- pipeline
def pipeline(shop, start, end) -> dict | None:
	if not _can(UNIT):
		return None
	steps = []
	for status in ACTIVE:
		f = _unit_filters(shop, status=status)
		steps.append({"status": status, "label": _(status), "count": _count(UNIT, f), "filters": f})
	released = _unit_filters(shop, released_on=["between", [str(start), f"{end} 23:59:59"]])
	shipped = _unit_filters(shop, status="Shipped", trulinx_ship_date=["between", [str(start), str(end)]])
	steps.append(
		{
			"status": "Released",
			"label": _("Released in period"),
			"count": _count(UNIT, released),
			"filters": released,
		}
	)
	steps.append(
		{
			"status": "Shipped",
			"label": _("Shipped in period"),
			"count": _count(UNIT, shipped),
			"filters": shipped,
		}
	)
	return {"steps": steps}


# --------------------------------------------------------------------------- needs attention
def _top(doctype, filters, field="name", n=4) -> str | None:
	rows = frappe.get_list(
		doctype, filters=filters, pluck=field, order_by="modified desc", limit_page_length=n
	)
	return ", ".join(r for r in rows if r) or None


def att_hold(shop):
	if not _can(UNIT):
		return None
	f = _unit_filters(shop, status="QC Hold")
	return _item(
		"hold", _("Units on QC Hold"), _count(UNIT, f), UNIT, f, "danger", _top(UNIT, f, "trulinx_work_order")
	)


def att_ready(shop):
	if not _can(UNIT):
		return None
	f = _unit_filters(shop, status="Ready for Release")
	return _item(
		"ready", _("Ready for release"), _count(UNIT, f), UNIT, f, "info", _top(UNIT, f, "trulinx_work_order")
	)


def att_flagged(shop):
	if not _can(UNIT):
		return None
	f = _unit_filters(shop, qc_flag=["is", "set"], status=["not in", ["Released", "Cancelled"]])
	return _item(
		"flag",
		_("Flagged by TrulinX (shipped or invoiced before QC release)"),
		_count(UNIT, f),
		UNIT,
		f,
		"danger",
	)


def att_late(shop):
	if not _can(UNIT):
		return None
	f = _unit_filters(shop, status=["in", ACTIVE], promised_date=["between", overdue_range()])
	return _item(
		"late",
		_("Past promised date, not released"),
		_count(UNIT, f),
		UNIT,
		f,
		"warning",
		_top(UNIT, f, "trulinx_work_order"),
	)


def att_old_drafts(shop):
	if not _can(INSP):
		return None
	f = _unit_filters(shop, docstatus=0, creation=["<", str(add_days(getdate(), -2))])
	return _item(
		"drafts", _("Draft inspections older than 2 days"), _count(INSP, f), INSP, {"docstatus": 0}, "warning"
	)


def att_needs_reinspection(shop):
	if not _can(INSP):
		return None
	f = _unit_filters(
		shop, docstatus=1, status="Rejected", inspection_date=[">=", str(add_days(getdate(), -180))]
	)
	rejected = frappe.get_list(INSP, filters=f, pluck="name", limit_page_length=0)
	if not rejected:
		return None
	redone = set(
		frappe.get_all(
			INSP,
			filters={"reinspection_of": ["in", rejected], "docstatus": ["!=", 2]},
			pluck="reinspection_of",
		)
	)
	waiting = [n for n in rejected if n not in redone]
	return _item(
		"reinspect",
		_("Rejected inspections with no re-inspection (180 days)"),
		len(waiting),
		INSP,
		{"name": ["in", waiting]},
		"danger",
		", ".join(waiting[:4]),
	)


def att_rework(shop):
	if not _can(NCR):
		return None
	f = {"record_type": "Rework", "status": "Open"}
	old = _count(NCR, {**f, "creation": ["<", str(add_days(getdate(), -7))]})
	return _item(
		"rework",
		_("Open Rework"),
		_count(NCR, f),
		NCR,
		f,
		"warning",
		_("{0} open more than 7 days").format(old) if old else None,
	)


def att_ncr(shop):
	if not _can(NCR):
		return None
	f = {"record_type": "NCR", "status": "Open"}
	crit = _count(NCR, {**f, "severity": "Critical"})
	return _item(
		"ncr",
		_("Open NCRs"),
		_count(NCR, f),
		NCR,
		f,
		"danger" if crit else "warning",
		_("{0} critical").format(crit) if crit else None,
	)


ATTENTION = [
	att_hold,
	att_flagged,
	att_needs_reinspection,
	att_late,
	att_ready,
	att_old_drafts,
	att_rework,
	att_ncr,
	lambda shop: att_capa_overdue(),
	lambda shop: att_scar_overdue(),
	lambda shop: att_calibration(),
]


# --------------------------------------------------------------------------- stage yield
def stage_yield(shop, start, end) -> list[dict] | None:
	if not (_can(INSP) and _can("QC Stage")):
		return None
	stages = {
		s.name: s
		for s in frappe.get_all(
			"QC Stage", fields=["name", "shop", "sequence", "job_type"], limit_page_length=0
		)
	}
	by_stage = {}
	for r in first_inspections(start, end):
		by_stage.setdefault(r.stage, []).append(r)
	out = []
	for name, rows in by_stage.items():
		meta = stages.get(name) or frappe._dict()
		if shop and meta.get("shop") and meta.get("shop") != shop:
			continue
		passed, total, rejected = fpy_summary(rows)
		out.append(
			{
				"stage": name,
				"shop": meta.get("shop") or (_("Repair") if meta.get("job_type") == "Repair" else ""),
				"sequence": meta.get("sequence") or 0,
				"passed": passed,
				"total": total,
				"pct": round(passed / total * 100, 1) if total else None,
				"rejected": rejected[:6],
			}
		)
	out.sort(key=lambda r: (r["shop"] or "zz", r["sequence"], r["stage"]))
	return out


# --------------------------------------------------------------------------- lists
def recent_inspections(shop) -> list[dict]:
	if not _can(INSP):
		return []
	return frappe.get_list(
		INSP,
		filters=_unit_filters(shop, docstatus=1),
		fields=["name", "qc_unit", "stage", "status", "inspection_date", "inspector_name", "is_reinspection"],
		order_by="inspection_date desc, modified desc",
		limit_page_length=8,
	)


def my_drafts() -> list[dict]:
	if not _can(INSP):
		return []
	return frappe.get_list(
		INSP,
		filters={"docstatus": 0, "owner": frappe.session.user},
		fields=["name", "qc_unit", "stage", "modified"],
		order_by="modified desc",
		limit_page_length=6,
	)


def qc_goals() -> list[str]:
	keys = [k for _g, ks in METRIC_GROUPS for k in ks if k in METRICS] + ["qc_stage_first_pass_yield"]
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
