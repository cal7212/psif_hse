# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Calculated metrics for ERPNext Quality Goals / Quality Reviews.

Each metric takes (period_start, period_end) as dates and returns (value, detail).
value is None when there is no data for the period; the objective is then left Open
for the reviewer. "Snapshot" metrics ignore the period and report the current state.
The same functions can back dashboard Number Cards later (see get_metric_value).
"""

from collections import Counter
from datetime import date, datetime, time, timedelta

import frappe
from frappe import _
from frappe.utils import add_days, add_months, flt, get_first_day, get_last_day, getdate, now_datetime

AT_LEAST, AT_MOST, EQUAL_TO, RECORD_ONLY = "At least", "At most", "Equal to", "Record only"
OPERATORS = (AT_LEAST, AT_MOST, EQUAL_TO, RECORD_ONLY)
OPERATOR_SYMBOLS = {AT_LEAST: "≥", AT_MOST: "≤", EQUAL_TO: "="}
PASSED, FAILED, OPEN = "Passed", "Failed", "Open"


# ---------------------------------------------------------------- periods
def get_review_period(frequency: str | None, ref_date=None) -> tuple[date, date]:
	"""The last complete period before ref_date (the review date)."""
	ref = getdate(ref_date)
	if frequency == "Daily":
		d = add_days(ref, -1)
		return getdate(d), getdate(d)
	if frequency == "Weekly":
		this_monday = add_days(ref, -ref.weekday())
		return getdate(add_days(this_monday, -7)), getdate(add_days(this_monday, -1))
	if frequency == "Quarterly":
		q_start_month = ((ref.month - 1) // 3) * 3 + 1
		this_q = date(ref.year, q_start_month, 1)
		prev_q = getdate(add_months(this_q, -3))
		return prev_q, getdate(add_days(this_q, -1))
	# Monthly and None: previous calendar month
	prev = getdate(add_months(get_first_day(ref), -1))
	return prev, getdate(get_last_day(prev))


def _bounds(start, end) -> tuple[datetime, datetime]:
	return datetime.combine(getdate(start), time.min), datetime.combine(getdate(end), time.max)


def _names(rows, limit=10) -> str:
	names = [r if isinstance(r, str) else r.name for r in rows]
	more = len(names) - limit
	return ", ".join(names[:limit]) + (f" (+{more} more)" if more > 0 else "")


def _exists(doctype: str) -> bool:
	return bool(frappe.db.exists("DocType", doctype))


# ---------------------------------------------------------------- HPU Build
def hpu_first_pass_yield(start, end):
	s, e = _bounds(start, end)
	units = frappe.get_all("HPU Unit", filters={"released_on": ["between", [s, e]]}, pluck="name")
	if not units:
		return None, _("No HPU Units released in the period.")
	rejected = set(
		frappe.get_all(
			"HPU Build Inspection",
			filters={"hpu_unit": ["in", units], "docstatus": 1, "status": "Rejected"},
			pluck="hpu_unit",
		)
	)
	first_pass = len(units) - len(rejected)
	detail = _("{0} of {1} released units passed every stage first time.").format(first_pass, len(units))
	if rejected:
		detail += " " + _("Had a rejection: {0}").format(_names(sorted(rejected)))
	return round(first_pass / len(units) * 100, 1), detail


def hpu_units_released(start, end):
	s, e = _bounds(start, end)
	units = frappe.get_all("HPU Unit", filters={"released_on": ["between", [s, e]]}, pluck="name")
	return len(units), _names(units) if units else _("None released.")


def hpu_shipped_before_release(start, end):
	units = frappe.get_all(
		"HPU Unit",
		filters={"trulinx_ship_date": ["between", [getdate(start), getdate(end)]], "qc_flag": ["is", "set"]},
		pluck="name",
	)
	return len(units), (_("Flagged: {0}").format(_names(units)) if units else _("None."))


def hpu_stage_rejections(start, end):
	s, e = _bounds(start, end)
	rows = frappe.get_all(
		"HPU Build Inspection",
		filters={"inspection_date": ["between", [s, e]], "docstatus": 1, "status": "Rejected"},
		pluck="stage",
	)
	if not rows:
		return 0, _("No rejected build inspections.")
	top = ", ".join(f"{stage}: {n}" for stage, n in Counter(rows).most_common(5))
	return len(rows), _("By stage: {0}").format(top)


# ---------------------------------------------------------------- Non Conformance
def nc_avg_days_to_resolve(start, end):
	s, e = _bounds(start, end)
	rows = frappe.get_all(
		"Non Conformance",
		filters={"status": "Resolved", "resolved_on": ["between", [s, e]]},
		fields=["name", "creation", "resolved_on"],
	)
	if not rows:
		return None, _("No Non Conformances resolved in the period.")
	days = [(r.resolved_on - r.creation).total_seconds() / 86400 for r in rows]
	slowest = max(rows, key=lambda r: r.resolved_on - r.creation)
	return round(sum(days) / len(days), 1), _("{0} resolved; slowest {1} ({2} days).").format(
		len(rows), slowest.name, round(max(days), 1)
	)


def nc_open_critical_over_7_days(start, end):
	cutoff = now_datetime() - timedelta(days=7)
	rows = frappe.get_all(
		"Non Conformance",
		filters={"status": "Open", "severity": "Critical", "creation": ["<", cutoff]},
		pluck="name",
	)
	return len(rows), (_("Open now: {0}").format(_names(rows)) if rows else _("None open."))


def nc_opened(start, end):
	s, e = _bounds(start, end)
	rows = frappe.get_all(
		"Non Conformance",
		filters={"creation": ["between", [s, e]], "status": ["!=", "Cancelled"]},
		fields=["name", "severity"],
	)
	if not rows:
		return 0, _("None opened.")
	by_sev = ", ".join(f"{sev or _('Not set')}: {n}" for sev, n in Counter(r.severity for r in rows).most_common())
	return len(rows), _("By severity: {0}").format(by_sev)


# ---------------------------------------------------------------- Asset inspections
def asset_inspection_on_time_pct(start, end):
	rows = frappe.get_all(
		"Asset Maintenance Log",
		filters={
			"due_date": ["between", [getdate(start), getdate(end)]],
			"maintenance_status": ["!=", "Cancelled"],
			"docstatus": ["<", 2],
		},
		fields=["name", "due_date", "completion_date", "maintenance_status"],
	)
	if not rows:
		return None, _("No maintenance/inspection tasks were due in the period.")
	late = [
		r
		for r in rows
		if not (
			r.maintenance_status == "Completed"
			and r.completion_date
			and getdate(r.completion_date) <= getdate(r.due_date)
		)
	]
	on_time = len(rows) - len(late)
	detail = _("{0} of {1} due tasks completed on or before the due date.").format(on_time, len(rows))
	if late:
		detail += " " + _("Late or open: {0}").format(_names(late))
	return round(on_time / len(rows) * 100, 1), detail


def assets_out_of_service(start, end):
	rows = frappe.get_all("Asset", filters={"safety_status": "Out of Service", "docstatus": 1}, pluck="name")
	return len(rows), (_names(rows) if rows else _("None."))


# ---------------------------------------------------------------- Housekeeping
def hk_avg_score(start, end):
	s, e = _bounds(start, end)
	rows = frappe.get_all(
		"Housekeeping Inspection",
		filters={"inspection_date": ["between", [s, e]], "docstatus": 1, "is_reinspection": 0},
		fields=["name", "housekeeping_area", "score"],
	)
	if not rows:
		return None, _("No housekeeping inspections in the period.")
	lowest = min(rows, key=lambda r: flt(r.score))
	return round(sum(flt(r.score) for r in rows) / len(rows), 1), _(
		"{0} inspections (re-inspections excluded); lowest {1}% in {2}."
	).format(len(rows), round(flt(lowest.score), 1), lowest.housekeeping_area)


def hk_areas_overdue(start, end):
	rows = frappe.get_all(
		"Housekeeping Area", filters={"disabled": 0, "schedule_status": "Overdue"}, pluck="name"
	)
	return len(rows), (_names(rows) if rows else _("None overdue."))


# ---------------------------------------------------------------- registry
# key: (label, function, default uom, snapshot?, required doctype)
METRICS = {
	"hpu_first_pass_yield": ("HPU first-pass yield (%)", hpu_first_pass_yield, "Percent", False, "HPU Unit"),
	"hpu_units_released": ("HPU units released", hpu_units_released, "Nos", False, "HPU Unit"),
	"hpu_shipped_before_release": (
		"HPU units shipped before QC release",
		hpu_shipped_before_release,
		"Nos",
		False,
		"HPU Unit",
	),
	"hpu_stage_rejections": (
		"HPU build inspections rejected",
		hpu_stage_rejections,
		"Nos",
		False,
		"HPU Build Inspection",
	),
	"nc_avg_days_to_resolve": (
		"Average days to resolve a Non Conformance",
		nc_avg_days_to_resolve,
		"Day",
		False,
		"Non Conformance",
	),
	"nc_open_critical_over_7_days": (
		"Critical Non Conformances open > 7 days (now)",
		nc_open_critical_over_7_days,
		"Nos",
		True,
		"Non Conformance",
	),
	"nc_opened": ("Non Conformances opened", nc_opened, "Nos", False, "Non Conformance"),
	"asset_inspection_on_time_pct": (
		"Asset maintenance/inspections on time (%)",
		asset_inspection_on_time_pct,
		"Percent",
		False,
		"Asset Maintenance Log",
	),
	"assets_out_of_service": ("Assets Out of Service (now)", assets_out_of_service, "Nos", True, "Asset"),
	"hk_avg_score": ("Housekeeping average score (%)", hk_avg_score, "Percent", False, "Housekeeping Inspection"),
	"hk_areas_overdue": ("Housekeeping areas overdue (now)", hk_areas_overdue, "Nos", True, "Housekeeping Area"),
}


def metric_options() -> str:
	return "\n" + "\n".join(METRICS)


def calculate(metric: str, start, end):
	if metric not in METRICS:
		return None, _("Unknown metric {0}.").format(metric)
	_label, fn, _uom, snapshot, doctype = METRICS[metric]
	if not _exists(doctype):
		return None, _("{0} is not installed on this site.").format(doctype)
	value, detail = fn(start, end)
	if snapshot:
		detail = _("As of {0}: {1}").format(frappe.format(now_datetime(), "Datetime"), detail)
	return value, detail


def evaluate(value, operator: str | None, target) -> str:
	if operator == RECORD_ONLY:
		return PASSED
	if value is None or operator not in OPERATOR_SYMBOLS:
		return OPEN
	value, target = flt(value), flt(target)
	if operator == AT_LEAST:
		return PASSED if value >= target else FAILED
	if operator == AT_MOST:
		return PASSED if value <= target else FAILED
	return PASSED if abs(value - target) < 1e-9 else FAILED


def target_text(operator: str | None, target, uom: str | None = None) -> str:
	if operator == RECORD_ONLY:
		return _("Record only")
	if operator not in OPERATOR_SYMBOLS:
		return ""
	unit = "%" if uom == "Percent" else (f" {uom}" if uom and uom != "Nos" else "")
	return f"{OPERATOR_SYMBOLS[operator]} {flt(target):g}{unit}"


@frappe.whitelist()
def get_metric_value(metric: str, period_start: str | None = None, period_end: str | None = None) -> dict:
	"""For dashboards / Number Cards. Defaults to the previous calendar month."""
	frappe.only_for(("Quality Manager", "System Manager"))
	if not (period_start and period_end):
		period_start, period_end = get_review_period("Monthly", getdate())
	value, detail = calculate(metric, period_start, period_end)
	return {"metric": metric, "value": value, "detail": detail, "period_start": period_start, "period_end": period_end}
