# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""HSE Home: one page for quick actions, items needing attention, live metrics and goals.

Everything is filtered by the signed-in user's read permissions; a section the user cannot
read is left out rather than shown empty."""

from datetime import date

import frappe
from frappe import _
from frappe.utils import add_days, add_months, date_diff, get_first_day, get_last_day, getdate

from hse.quality_metrics.metrics import (
	METRICS,
	RECORD_ONLY,
	calculate,
	evaluate,
	target_text,
)

PERIODS = {
	"this_month": "This month",
	"last_month": "Last month",
	"last_90_days": "Last 90 days",
	"year_to_date": "Year to date",
}

# Metric groups shown on the page (keys from hse.quality_metrics.metrics.METRICS)
METRIC_GROUPS = [
	("Shop QC", ["hpu_first_pass_yield", "hpu_units_released", "hpu_shipped_before_release"]),
	("Rework, NCR and CAPA", ["rework_opened", "nc_opened", "capa_overdue", "capa_closed_on_time_pct"]),
	("Equipment and Housekeeping", ["asset_inspection_on_time_pct", "assets_out_of_service", "hk_avg_score"]),
	("Training", ["training_compliance_pct", "training_overdue"]),
	("Repairs", ["rga_received", "repair_turnaround_days"]),
]

DRAFT_DOCTYPES = {
	"QC Inspection": ["qc_unit", "stage"],
	"Asset Inspection": ["asset_name", "template"],
	"Housekeeping Inspection": ["housekeeping_area", "template"],
	"Injury_Illness Report": ["employee_name", "type_of_incident"],
	"Competency Evaluation": ["employee_name"],
}

HSE_MODULES = (
	"HSE",
	"Asset Inspection",
	"Housekeeping Inspection",
	"Shop QC",
	"Quality Metrics",
	"Training Matrix",
)


def period_bounds(period: str, today: date | None = None) -> tuple[date, date]:
	today = getdate(today)
	if period == "last_month":
		start = getdate(add_months(get_first_day(today), -1))
		return start, getdate(get_last_day(start))
	if period == "last_90_days":
		return getdate(add_days(today, -89)), today
	if period == "year_to_date":
		return date(today.year, 1, 1), today
	return getdate(get_first_day(today)), today


def _can(doctype: str) -> bool:
	return bool(frappe.db.exists("DocType", doctype)) and frappe.has_permission(doctype, "read")


def _count(doctype: str, filters) -> int:
	return len(frappe.get_list(doctype, filters=filters, pluck="name", limit_page_length=0))


def _safe(fn, *args):
	try:
		return fn(*args)
	except Exception:
		frappe.log_error(title=f"HSE Home: {getattr(fn, '__name__', fn)}")
		return None


@frappe.whitelist()
def get_home(period: str = "this_month") -> dict:
	if period not in PERIODS:
		period = "this_month"
	start, end = period_bounds(period)
	return {
		"user": frappe.utils.get_fullname(frappe.session.user),
		"today": str(getdate()),
		"period": {"key": period, "label": _(PERIODS[period]), "start": str(start), "end": str(end)},
		"periods": [{"key": k, "label": _(v)} for k, v in PERIODS.items()],
		"safety": _safe(safety_summary),
		"attention": [a for a in (_safe(fn) for fn in ATTENTION) if a],
		"my_work": _safe(my_work, frappe.session.user) or {"drafts": [], "todos": []},
		"metrics": _safe(metric_groups, start, end) or [],
		"reviews": _safe(latest_reviews) or [],
	}


# --------------------------------------------------------------------------- safety banner
def safety_summary() -> dict | None:
	dt = "Injury_Illness Report"
	if not _can(dt):
		return None
	last = frappe.get_list(
		dt,
		filters={"is_recordable": 1, "docstatus": ["!=", 2]},
		fields=["incident_date"],
		order_by="incident_date desc",
		limit_page_length=1,
	)
	last_date = last[0].incident_date if last and last[0].incident_date else None
	open_reports = _count(
		dt, {"docstatus": ["!=", 2], "status": ["in", ["To-Do", "In Progress", "Reopened"]]}
	)
	actions_late = _count(
		dt,
		{"docstatus": ["!=", 2], "date_due": ["<", getdate()], "date_done": ["is", "not set"]},
	)
	return {
		"days_since_recordable": date_diff(getdate(), last_date) if last_date else None,
		"last_recordable": str(last_date) if last_date else None,
		"open_reports": open_reports,
		"actions_overdue": actions_late,
	}


# --------------------------------------------------------------------------- needs attention
def _item(key, label, count, doctype, route_options=None, level="warning", detail=None, route=None):
	if not count:
		return None
	return {
		"key": key,
		"label": label,
		"count": count,
		"doctype": doctype,
		"route": route,
		"route_options": route_options or {},
		"level": level,
		"detail": detail,
	}


def att_qc_hold():
	if not _can("QC Unit"):
		return None
	f = {"status": "QC Hold"}
	return _item("qc_hold", _("Units on QC Hold"), _count("QC Unit", f), "QC Unit", f, "danger")


def att_ready_release():
	if not _can("QC Unit"):
		return None
	f = {"status": "Ready for Release"}
	return _item("ready", _("Units ready for release"), _count("QC Unit", f), "QC Unit", f, "info")


def att_open_rework():
	if not _can("Nonconformance Report"):
		return None
	f = {"record_type": "Rework", "status": "Open"}
	return _item("rework", _("Open Rework"), _count("Nonconformance Report", f), "Nonconformance Report", f)


def att_open_ncr():
	if not _can("Nonconformance Report"):
		return None
	f = {"record_type": "NCR", "status": "Open"}
	n = _count("Nonconformance Report", f)
	crit = _count("Nonconformance Report", {**f, "severity": "Critical"})
	detail = _("{0} critical").format(crit) if crit else None
	return _item(
		"ncr", _("Open NCRs"), n, "Nonconformance Report", f, "danger" if crit else "warning", detail
	)


def att_capa_overdue():
	if not _can("Nonconformance Report"):
		return None
	count, detail = calculate("capa_overdue", None, None)
	return _item(
		"capa",
		_("CAPAs past a due date"),
		count,
		"Nonconformance Report",
		{"capa_required": 1, "capa_status": ["not in", ["Closed", "Cancelled"]]},
		"danger",
		detail,
	)


def att_scar_overdue():
	if not _can("Nonconformance Report"):
		return None
	f = {"scar_status": "Issued", "scar_response_due": ["<", str(getdate())]}
	return _item(
		"scar", _("SCAR responses overdue"), _count("Nonconformance Report", f), "Nonconformance Report", f
	)


def att_hk_overdue():
	if not _can("Housekeeping Area"):
		return None
	f = {"disabled": 0, "schedule_status": "Overdue"}
	due = _count("Housekeeping Area", {"disabled": 0, "schedule_status": "Due"})
	return _item(
		"hk",
		_("Housekeeping areas overdue"),
		_count("Housekeeping Area", f),
		"Housekeeping Area",
		f,
		"warning",
		_("{0} more due now").format(due) if due else None,
	)


def att_hk_due():
	if not _can("Housekeeping Area"):
		return None
	if _count("Housekeeping Area", {"disabled": 0, "schedule_status": "Overdue"}):
		return None  # shown as detail on the overdue item
	f = {"disabled": 0, "schedule_status": "Due"}
	return _item(
		"hk_due", _("Housekeeping areas due"), _count("Housekeeping Area", f), "Housekeeping Area", f, "info"
	)


def att_assets_out():
	if not _can("Asset"):
		return None
	f = {"safety_status": "Out of Service", "docstatus": 1}
	return _item("assets_out", _("Assets out of service"), _count("Asset", f), "Asset", f, "danger")


def att_maintenance_late():
	if not _can("Asset Maintenance Log"):
		return None
	f = {"maintenance_status": ["in", ["Planned", "Overdue"]], "due_date": ["<", str(getdate())]}
	return _item(
		"maint",
		_("Asset inspections / maintenance overdue"),
		_count("Asset Maintenance Log", f),
		"Asset Maintenance Log",
		f,
	)


def att_calibration():
	if not _can("Measuring Instrument"):
		return None
	today = getdate()
	base = {"status": "Active", "calibration_required": 1}
	late = {**base, "calibration_due": ["<", str(today)]}
	soon = _count(
		"Measuring Instrument",
		{**base, "calibration_due": ["between", [str(today), str(add_days(today, 30))]]},
	)
	return _item(
		"cal",
		_("Instruments past calibration"),
		_count("Measuring Instrument", late),
		"Measuring Instrument",
		late,
		"danger",
		_("{0} more due in 30 days").format(soon) if soon else None,
	)


def att_training_overdue():
	if not _can("Employee Training Matrix"):
		return None
	count, detail = calculate("training_overdue", None, None)
	return _item(
		"training",
		_("Required training overdue"),
		count,
		"Employee Training Matrix",
		None,
		"warning",
		detail,
	)


def att_training_requests():
	if not _can("Training Request"):
		return None
	f = {"status": "Pending"}
	return _item(
		"treq", _("Training requests to decide"), _count("Training Request", f), "Training Request", f, "info"
	)


def att_sds_review():
	if not _can("SDS"):
		return None
	f = {"status": "Active", "next_review_date": ["<=", str(getdate())]}
	return _item("sds", _("SDS reviews due"), _count("SDS", f), "SDS", f, "info")


def att_injury_open():
	if not _can("Injury_Illness Report"):
		return None
	f = {"docstatus": ["!=", 2], "status": ["in", ["To-Do", "In Progress", "Reopened"]]}
	return _item(
		"injury",
		_("Open injury / incident reports"),
		_count("Injury_Illness Report", f),
		"Injury_Illness Report",
		f,
	)


ATTENTION = [
	att_qc_hold,
	att_assets_out,
	att_capa_overdue,
	att_open_ncr,
	att_calibration,
	att_injury_open,
	att_open_rework,
	att_scar_overdue,
	att_hk_overdue,
	att_hk_due,
	att_maintenance_late,
	att_training_overdue,
	att_training_requests,
	att_sds_review,
	att_ready_release,
]


# --------------------------------------------------------------------------- my work
def my_work(user: str) -> dict:
	drafts = []
	for dt, fields in DRAFT_DOCTYPES.items():
		if not _can(dt):
			continue
		meta = frappe.get_meta(dt)
		fields = [f for f in fields if meta.has_field(f)]
		for r in frappe.get_list(
			dt,
			filters={"docstatus": 0, "owner": user},
			fields=["name", "modified", *fields],
			order_by="modified desc",
			limit_page_length=5,
		):
			drafts.append(
				{
					"doctype": dt,
					"name": r.name,
					"modified": str(r.modified),
					"subtitle": " · ".join(str(r.get(f)) for f in fields if r.get(f)),
				}
			)
	drafts.sort(key=lambda d: d["modified"], reverse=True)

	hse_doctypes = frappe.get_all("DocType", filters={"module": ["in", HSE_MODULES]}, pluck="name")
	todos = frappe.get_all(
		"ToDo",
		filters={"allocated_to": user, "status": "Open", "reference_type": ["in", hse_doctypes]},
		fields=["name", "reference_type", "reference_name", "description", "date", "priority"],
		order_by="date asc, creation desc",
		limit_page_length=10,
	)
	for t in todos:
		t.description = frappe.utils.strip_html(t.description or "")[:140]
		t.date = str(t.date) if t.date else None
	return {"drafts": drafts[:10], "todos": todos}


# --------------------------------------------------------------------------- metrics and goals
def _goal_targets(keys: list[str]) -> dict:
	"""First goal target (not Record only) for each metric."""
	rows = frappe.get_all(
		"Quality Goal Objective",
		filters={"parenttype": "Quality Goal", "hse_metric": ["in", keys]},
		fields=["hse_metric", "target_operator", "target_value", "parent"],
		order_by="parent asc, idx asc",
	)
	out = {}
	for r in rows:
		if r.target_operator and r.target_operator != RECORD_ONLY and r.hse_metric not in out:
			out[r.hse_metric] = r
	return out


def metric_groups(start, end) -> list[dict]:
	keys = [k for _g, ks in METRIC_GROUPS for k in ks if k in METRICS]
	targets = _goal_targets(keys) if frappe.db.has_column("Quality Goal Objective", "hse_metric") else {}
	groups = []
	for group, ks in METRIC_GROUPS:
		items = []
		for key in ks:
			if key not in METRICS:
				continue
			label, _fn, uom, snapshot, doctype = METRICS[key]
			if not _can(doctype):
				continue
			value, detail = calculate(key, start, end)
			t = targets.get(key)
			items.append(
				{
					"key": key,
					"label": _(label),
					"value": value,
					"uom": uom,
					"snapshot": snapshot,
					"detail": detail,
					"doctype": doctype,
					"target": target_text(t.target_operator, t.target_value, uom) if t else None,
					"goal": t.parent if t else None,
					"status": evaluate(value, t.target_operator, t.target_value) if t else None,
				}
			)
		if items:
			groups.append({"group": _(group), "items": items})
	return groups


def latest_reviews() -> list[dict]:
	if not (_can("Quality Review") and _can("Quality Goal")):
		return []
	goals = frappe.get_list("Quality Goal", pluck="name", order_by="name asc", limit_page_length=0)
	out = []
	for g in goals:
		r = frappe.get_list(
			"Quality Review",
			filters={"goal": g},
			fields=["name", "date", "status"],
			order_by="date desc, creation desc",
			limit_page_length=1,
		)
		out.append(
			{
				"goal": g,
				"review": r[0].name if r else None,
				"date": str(r[0].date) if r and r[0].date else None,
				"status": r[0].status if r else None,
			}
		)
	return out
