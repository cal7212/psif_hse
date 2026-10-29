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


# ---------------------------------------------------------------- Shop QC
# Metric keys keep their original hpu_* names so existing Quality Goals keep working;
# they now cover every shop.
def hpu_first_pass_yield(start, end):
	s, e = _bounds(start, end)
	units = frappe.get_all("QC Unit", filters={"released_on": ["between", [s, e]]}, pluck="name")
	if not units:
		return None, _("No QC Units released in the period.")
	rejected = set(
		frappe.get_all(
			"QC Inspection",
			filters={"qc_unit": ["in", units], "docstatus": 1, "status": "Rejected"},
			pluck="qc_unit",
		)
	)
	first_pass = len(units) - len(rejected)
	detail = _("{0} of {1} released units passed every stage first time.").format(first_pass, len(units))
	if rejected:
		detail += " " + _("Had a rejection: {0}").format(_names(sorted(rejected)))
	return round(first_pass / len(units) * 100, 1), detail


# First-pass yield per QC Stage. A unit passes a stage first time when its first submitted,
# original (not re-) inspection at that stage in the period is Accepted.
def first_inspections(start, end, stage: str | None = None) -> list[dict]:
	s, e = _bounds(start, end)
	filters = {
		"inspection_date": ["between", [s, e]],
		"docstatus": 1,
		"is_reinspection": 0,
		"reinspection_of": ["is", "not set"],
	}
	if stage:
		filters["stage"] = stage
	rows = frappe.get_all(
		"QC Inspection",
		filters=filters,
		fields=["name", "qc_unit", "stage", "status", "inspection_date"],
		order_by="inspection_date asc, creation asc",
	)
	first, seen = [], set()
	for r in rows:
		key = (r.qc_unit, r.stage)
		if key not in seen:
			seen.add(key)
			first.append(r)
	return first


def fpy_summary(rows) -> tuple[int, int, list[str]]:
	"""(passed, total, rejected inspection names) for first-inspection rows."""
	rejected = [r.name for r in rows if r.status == "Rejected"]
	return len(rows) - len(rejected), len(rows), rejected


def qc_stage_first_pass_yield(start, end, stage):
	rows = first_inspections(start, end, stage)
	if not rows:
		return None, _("No first inspections at {0} in the period.").format(stage)
	passed, total, rejected = fpy_summary(rows)
	detail = _("{0} of {1} units passed {2} on the first inspection.").format(passed, total, stage)
	if rejected:
		detail += " " + _("Rejected: {0}").format(_names(rejected))
	return round(passed / total * 100, 1), detail


def qc_first_pass_yield_by_stage(start, end):
	rows = first_inspections(start, end)
	if not rows:
		return None, _("No first inspections in the period.")
	passed, total, _rejected = fpy_summary(rows)
	by_stage = {}
	for r in rows:
		by_stage.setdefault(r.stage, []).append(r)
	parts = []
	for stage_name, stage_rows in sorted(by_stage.items(), key=lambda kv: fpy_summary(kv[1])[0] / len(kv[1])):
		p, t, _r = fpy_summary(stage_rows)
		parts.append(f"{stage_name}: {p}/{t} ({round(p / t * 100, 1):g}%)")
	detail = _("{0} of {1} first inspections passed. By stage, lowest first: {2}").format(
		passed, total, "; ".join(parts)
	)
	return round(passed / total * 100, 1), detail


def hpu_units_released(start, end):
	s, e = _bounds(start, end)
	units = frappe.get_all(
		"QC Unit", filters={"released_on": ["between", [s, e]]}, fields=["name", "shop"], order_by="name"
	)
	if not units:
		return 0, _("None released.")
	by_shop = ", ".join(f"{shop or '-'}: {n}" for shop, n in Counter(u.shop for u in units).most_common())
	return len(units), _("By shop: {0}").format(by_shop)


def hpu_shipped_before_release(start, end):
	units = frappe.get_all(
		"QC Unit",
		filters={"trulinx_ship_date": ["between", [getdate(start), getdate(end)]], "qc_flag": ["is", "set"]},
		pluck="name",
	)
	return len(units), (_("Flagged: {0}").format(_names(units)) if units else _("None."))


def hpu_stage_rejections(start, end):
	s, e = _bounds(start, end)
	rows = frappe.get_all(
		"QC Inspection",
		filters={"inspection_date": ["between", [s, e]], "docstatus": 1, "status": "Rejected"},
		pluck="stage",
	)
	if not rows:
		return 0, _("No rejected QC inspections.")
	top = ", ".join(f"{stage}: {n}" for stage, n in Counter(rows).most_common(5))
	return len(rows), _("By stage: {0}").format(top)


def rga_received(start, end):
	rows = frappe.get_all(
		"QC Unit",
		filters={"job_type": "Repair", "received_date": ["between", [getdate(start), getdate(end)]]},
		fields=["name", "shop"],
	)
	if not rows:
		return 0, _("No RGAs received.")
	by_shop = ", ".join(f"{shop or '-'}: {n}" for shop, n in Counter(r.shop for r in rows).most_common())
	return len(rows), _("By shop: {0}").format(by_shop)


def repair_turnaround_days(start, end):
	s, e = _bounds(start, end)
	rows = frappe.get_all(
		"QC Unit",
		filters={"job_type": "Repair", "released_on": ["between", [s, e]], "received_date": ["is", "set"]},
		fields=["name", "received_date", "released_on"],
	)
	if not rows:
		return None, _("No repairs released in the period.")
	days = [(getdate(r.released_on) - getdate(r.received_date)).days for r in rows]
	return round(sum(days) / len(days), 1), _("{0} repairs; longest {1} days.").format(len(rows), max(days))


def repair_failure_causes(start, end):
	rows = frappe.get_all(
		"QC Unit",
		filters={
			"job_type": "Repair",
			"received_date": ["between", [getdate(start), getdate(end)]],
			"failure_cause": ["is", "set"],
		},
		pluck="failure_cause",
	)
	if not rows:
		return 0, _("No failure causes recorded.")
	top = ", ".join(f"{cause}: {n}" for cause, n in Counter(rows).most_common(5))
	return len(rows), _("Top causes: {0}").format(top)


# ---------------------------------------------------------------- Nonconformance Report
# QM-104 Rev. 3: the NCR metrics count formal NCRs only; Rework is counted separately.
NOT_REWORK = {"record_type": ["!=", "Rework"]}


def rework_opened(start, end):
	s, e = _bounds(start, end)
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={"creation": ["between", [s, e]], "record_type": "Rework"},
		fields=["name", "status", "escalated_to"],
	)
	if not rows:
		return 0, _("None opened.")
	escalated = [r.name for r in rows if r.escalated_to]
	still_open = [r.name for r in rows if r.status == "Open"]
	return len(rows), _("Open: {0}; escalated to NCR: {1}").format(len(still_open), len(escalated))


def nc_avg_days_to_resolve(start, end):
	s, e = _bounds(start, end)
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={"status": "Resolved", "resolved_on": ["between", [s, e]], **NOT_REWORK},
		fields=["name", "creation", "resolved_on"],
	)
	if not rows:
		return None, _("No Nonconformance Reports resolved in the period.")
	days = [(r.resolved_on - r.creation).total_seconds() / 86400 for r in rows]
	slowest = max(rows, key=lambda r: r.resolved_on - r.creation)
	return round(sum(days) / len(days), 1), _("{0} resolved; slowest {1} ({2} days).").format(
		len(rows), slowest.name, round(max(days), 1)
	)


def nc_open_critical_over_7_days(start, end):
	cutoff = now_datetime() - timedelta(days=7)
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={"status": "Open", "severity": "Critical", "creation": ["<", cutoff], **NOT_REWORK},
		pluck="name",
	)
	return len(rows), (_("Open now: {0}").format(_names(rows)) if rows else _("None open."))


def nc_opened(start, end):
	s, e = _bounds(start, end)
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={"creation": ["between", [s, e]], "status": ["!=", "Cancelled"], **NOT_REWORK},
		fields=["name", "severity"],
	)
	if not rows:
		return 0, _("None opened.")
	by_sev = ", ".join(
		f"{sev or _('Not set')}: {n}" for sev, n in Counter(r.severity for r in rows).most_common()
	)
	return len(rows), _("By severity: {0}").format(by_sev)


IS_REWORK = {"record_type": "Rework"}
CAPA_DONE = ("Closed", "Cancelled")


def _pct(part: int, whole: int) -> float:
	return round(part / whole * 100, 1)


def _avg_days(rows, start_field: str, end_field: str) -> tuple[float, dict]:
	def days(r):
		a, b = r.get(start_field), r.get(end_field)
		if isinstance(a, datetime) and isinstance(b, datetime):
			return (b - a).total_seconds() / 86400
		return (getdate(b) - getdate(a)).days

	values = [(days(r), r) for r in rows]
	slowest = max(values, key=lambda v: v[0])
	return round(sum(v for v, _r in values) / len(values), 1), {
		"name": slowest[1].name,
		"days": round(slowest[0], 1),
	}


# Rework
def rework_escalation_pct(start, end):
	s, e = _bounds(start, end)
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={"creation": ["between", [s, e]], "status": ["!=", "Cancelled"], **IS_REWORK},
		fields=["name", "escalated_to"],
	)
	if not rows:
		return None, _("No Rework records opened in the period.")
	escalated = [r.name for r in rows if r.escalated_to]
	detail = _("{0} of {1} Rework records opened in the period were escalated to an NCR.").format(
		len(escalated), len(rows)
	)
	if escalated:
		detail += " " + _("Escalated: {0}").format(_names(escalated))
	return _pct(len(escalated), len(rows)), detail


def rework_avg_days_to_close(start, end):
	s, e = _bounds(start, end)
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={"status": "Resolved", "resolved_on": ["between", [s, e]], **IS_REWORK},
		fields=["name", "creation", "resolved_on"],
	)
	if not rows:
		return None, _("No Rework records closed in the period.")
	avg, slowest = _avg_days(rows, "creation", "resolved_on")
	return avg, _("{0} closed; slowest {1} ({2} days).").format(len(rows), slowest["name"], slowest["days"])


def rework_accept_pct(start, end):
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={
			"rw_inspected_date": ["between", [getdate(start), getdate(end)]],
			"rw_quality_verification": ["in", ["Accept", "Reject"]],
			**IS_REWORK,
		},
		fields=["name", "rw_quality_verification"],
	)
	if not rows:
		return None, _("No Rework verifications in the period.")
	rejected = [r.name for r in rows if r.rw_quality_verification == "Reject"]
	detail = _("{0} of {1} Rework verifications accepted.").format(len(rows) - len(rejected), len(rows))
	if rejected:
		detail += " " + _("Rejected: {0}").format(_names(rejected))
	return _pct(len(rows) - len(rejected), len(rows)), detail


def rework_open_over_7_days(start, end):
	cutoff = now_datetime() - timedelta(days=7)
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={"status": "Open", "creation": ["<", cutoff], **IS_REWORK},
		pluck="name",
	)
	return len(rows), (_("Open now: {0}").format(_names(rows)) if rows else _("None open."))


# NCR
def nc_open_over_30_days(start, end):
	cutoff = now_datetime() - timedelta(days=30)
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={"status": "Open", "creation": ["<", cutoff], **NOT_REWORK},
		pluck="name",
	)
	return len(rows), (_("Open now: {0}").format(_names(rows)) if rows else _("None open."))


def nc_by_source(start, end):
	s, e = _bounds(start, end)
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={"creation": ["between", [s, e]], "status": ["!=", "Cancelled"], **NOT_REWORK},
		fields=["name", "source", "disposition"],
	)
	if not rows:
		return 0, _("None opened.")
	src = ", ".join(f"{k or _('Not set')}: {n}" for k, n in Counter(r.source for r in rows).most_common())
	disp = ", ".join(
		f"{k or _('Not set')}: {n}" for k, n in Counter(r.disposition for r in rows).most_common()
	)
	return len(rows), _("By source: {0}. By disposition: {1}").format(src, disp)


def nc_capa_pct(start, end):
	s, e = _bounds(start, end)
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={"creation": ["between", [s, e]], "status": ["!=", "Cancelled"], **NOT_REWORK},
		fields=["name", "capa_required"],
	)
	if not rows:
		return None, _("No NCRs opened in the period.")
	capa = [r.name for r in rows if r.capa_required]
	return _pct(len(capa), len(rows)), _("{0} of {1} NCRs opened in the period required a CAPA.").format(
		len(capa), len(rows)
	)


# CAPA (QM-128), recorded on the Nonconformance Report
IS_CAPA = {"capa_required": 1}


def capa_opened(start, end):
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={"capa_initiated_date": ["between", [getdate(start), getdate(end)]], **IS_CAPA},
		fields=["name", "capa_no", "capa_source"],
	)
	if not rows:
		return 0, _("None opened.")
	by_src = ", ".join(
		f"{k or _('Not set')}: {n}" for k, n in Counter(r.capa_source for r in rows).most_common()
	)
	return len(rows), _("By source: {0}").format(by_src)


def capa_open(start, end):
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={"capa_status": ["not in", CAPA_DONE], **IS_CAPA},
		fields=["name", "capa_no", "capa_status"],
	)
	if not rows:
		return 0, _("None open.")
	by_status = ", ".join(
		f"{k or _('Not set')}: {n}" for k, n in Counter(r.capa_status for r in rows).most_common()
	)
	return len(rows), _("By status: {0}").format(by_status)


def _capa_label(r) -> str:
	return f"{r.capa_no} ({r.name})" if r.get("capa_no") else r.name


def capa_overdue(start, end):
	today = getdate()
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={"capa_status": ["not in", CAPA_DONE], **IS_CAPA},
		fields=[
			"name",
			"capa_no",
			"capa_status",
			"capa_containment_due",
			"capa_correction_due",
			"capa_closure_due",
		],
	)
	late = []
	for r in rows:
		if r.capa_closure_due and getdate(r.capa_closure_due) < today:
			late.append(_("{0}: closure due {1}").format(_capa_label(r), r.capa_closure_due))
		elif (
			r.capa_status in ("Open", "Containment", "Investigation", "Corrective Action")
			and r.capa_correction_due
			and getdate(r.capa_correction_due) < today
		):
			late.append(_("{0}: correction due {1}").format(_capa_label(r), r.capa_correction_due))
		elif (
			r.capa_status in ("Open", "Containment")
			and r.capa_containment_due
			and getdate(r.capa_containment_due) < today
		):
			late.append(_("{0}: containment due {1}").format(_capa_label(r), r.capa_containment_due))
	return len(late), ("; ".join(late[:10]) if late else _("None overdue."))


def capa_closed_on_time_pct(start, end):
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={
			"capa_status": "Closed",
			"capa_closure_date": ["between", [getdate(start), getdate(end)]],
			**IS_CAPA,
		},
		fields=["name", "capa_no", "capa_closure_date", "capa_closure_due"],
	)
	if not rows:
		return None, _("No CAPAs closed in the period.")
	late = [
		r for r in rows if r.capa_closure_due and getdate(r.capa_closure_date) > getdate(r.capa_closure_due)
	]
	detail = _("{0} of {1} CAPAs closed by the closure due date.").format(len(rows) - len(late), len(rows))
	if late:
		detail += " " + _("Late: {0}").format(", ".join(_capa_label(r) for r in late[:10]))
	return _pct(len(rows) - len(late), len(rows)), detail


def capa_avg_days_to_close(start, end):
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={
			"capa_status": "Closed",
			"capa_closure_date": ["between", [getdate(start), getdate(end)]],
			"capa_initiated_date": ["is", "set"],
			**IS_CAPA,
		},
		fields=["name", "capa_initiated_date", "capa_closure_date"],
	)
	if not rows:
		return None, _("No CAPAs closed in the period.")
	avg, slowest = _avg_days(rows, "capa_initiated_date", "capa_closure_date")
	return avg, _("{0} closed; slowest {1} ({2} days).").format(len(rows), slowest["name"], slowest["days"])


def capa_effective_pct(start, end):
	rows = frappe.get_all(
		"Nonconformance Report",
		filters={
			"capa_verification_date": ["between", [getdate(start), getdate(end)]],
			"capa_quality_verification": ["in", ["Effective", "Not Effective"]],
			**IS_CAPA,
		},
		fields=["name", "capa_no", "capa_quality_verification"],
	)
	if not rows:
		return None, _("No CAPA effectiveness checks in the period.")
	not_eff = [r for r in rows if r.capa_quality_verification == "Not Effective"]
	detail = _("{0} of {1} CAPAs verified Effective.").format(len(rows) - len(not_eff), len(rows))
	if not_eff:
		detail += " " + _("Not Effective: {0}").format(", ".join(_capa_label(r) for r in not_eff[:10]))
	return _pct(len(rows) - len(not_eff), len(rows)), detail


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


# ---------------------------------------------------------------- Training Matrix (TRN-700 Rev 1)
def _required_training_rows(extra=None):
	filters = {"parenttype": "Employee Training Matrix", "active": 1, "is_required": 1}
	filters.update(extra or {})
	return frappe.get_all(
		"Employee Training Matrix Item",
		filters=filters,
		fields=["employee_name", "training_requirement", "status", "qualification"],
	)


def training_compliance_pct(start, end):
	rows = _required_training_rows()
	if not rows:
		return None, _("No required training on any active employee's matrix.")
	qualified = sum(1 for r in rows if r.qualification == "Qualified")
	return round(qualified / len(rows) * 100, 1), _(
		"{0} of {1} required training items Qualified across active employees."
	).format(qualified, len(rows))


def _overdue_detail(rows):
	if not rows:
		return _("None overdue.")
	by_course = Counter(r.training_requirement for r in rows)
	top = ", ".join(f"{c} ({n})" for c, n in by_course.most_common(5))
	return _("{0} employees affected. Most overdue: {1}").format(len({r.employee_name for r in rows}), top)


def training_overdue(start, end):
	rows = _required_training_rows({"status": "Overdue"})
	return len(rows), _overdue_detail(rows)


def training_high_hazard_overdue(start, end):
	rows = _required_training_rows({"status": "Overdue", "high_hazard": 1})
	return len(rows), _overdue_detail(rows)


def training_onboarding_on_time_pct(start, end):
	"""Hire-based courses (orientation, QMS Awareness, HR onboarding) whose first deadline fell in
	the period: share completed by that deadline (TRN-700 §4.3, §4.5)."""
	courses = {
		r.name: r.initial_due_days
		for r in frappe.get_all(
			"Training Requirement",
			filters={"initial_due_basis": "Date of Hire"},
			fields=["name", "initial_due_days"],
		)
	}
	if not courses:
		return None, _("No hire-based training requirements.")
	matrices = {
		m.name: m.date_of_joining
		for m in frappe.get_all(
			"Employee Training Matrix",
			filters={"date_of_joining": ["is", "set"]},
			fields=["name", "date_of_joining"],
		)
	}
	rows = frappe.get_all(
		"Employee Training Matrix Item",
		filters={
			"parenttype": "Employee Training Matrix",
			"is_required": 1,
			"training_requirement": ["in", list(courses)],
		},
		fields=["parent", "training_requirement", "first_completed_on"],
	)
	start, end = getdate(start), getdate(end)
	due_in_period, on_time = 0, 0
	for r in rows:
		hired = matrices.get(r.parent)
		if not hired:
			continue
		deadline = getdate(add_days(hired, courses[r.training_requirement] or 0))
		if not (start <= deadline <= end):
			continue
		due_in_period += 1
		on_time += bool(r.first_completed_on and getdate(r.first_completed_on) <= deadline)
	if not due_in_period:
		return None, _("No new-hire training deadlines fell in the period.")
	return round(on_time / due_in_period * 100, 1), _(
		"{0} of {1} new-hire training deadlines met in the period."
	).format(on_time, due_in_period)


# ---------------------------------------------------------------- registry
# key: (label, function, default uom, snapshot?, required doctype)
METRICS = {
	"hpu_first_pass_yield": (
		"QC first-pass yield, all shops (%)",
		hpu_first_pass_yield,
		"Percent",
		False,
		"QC Unit",
	),
	"qc_stage_first_pass_yield": (
		"First-pass yield at a QC Stage (%)",
		qc_stage_first_pass_yield,
		"Percent",
		False,
		"QC Inspection",
	),
	"qc_first_pass_yield_by_stage": (
		"First-pass yield, all stages, with stage breakdown (%)",
		qc_first_pass_yield_by_stage,
		"Percent",
		False,
		"QC Inspection",
	),
	"hpu_units_released": ("QC units released", hpu_units_released, "Nos", False, "QC Unit"),
	"hpu_shipped_before_release": (
		"Units shipped before QC release",
		hpu_shipped_before_release,
		"Nos",
		False,
		"QC Unit",
	),
	"hpu_stage_rejections": (
		"QC inspections rejected",
		hpu_stage_rejections,
		"Nos",
		False,
		"QC Inspection",
	),
	"rga_received": ("RGAs received", rga_received, "Nos", False, "QC Unit"),
	"repair_turnaround_days": (
		"Average repair turnaround (received to release, days)",
		repair_turnaround_days,
		"Day",
		False,
		"QC Unit",
	),
	"repair_failure_causes": ("Repairs with a failure cause", repair_failure_causes, "Nos", False, "QC Unit"),
	"nc_avg_days_to_resolve": (
		"Average days to resolve an NCR (excludes Rework)",
		nc_avg_days_to_resolve,
		"Day",
		False,
		"Nonconformance Report",
	),
	"nc_open_critical_over_7_days": (
		"Critical NCRs open > 7 days (now)",
		nc_open_critical_over_7_days,
		"Nos",
		True,
		"Nonconformance Report",
	),
	"nc_opened": ("NCRs opened (excludes Rework)", nc_opened, "Nos", False, "Nonconformance Report"),
	"rework_opened": ("Rework records opened", rework_opened, "Nos", False, "Nonconformance Report"),
	"rework_escalation_pct": (
		"Rework escalated to NCR (%)",
		rework_escalation_pct,
		"Percent",
		False,
		"Nonconformance Report",
	),
	"rework_avg_days_to_close": (
		"Average days to close a Rework",
		rework_avg_days_to_close,
		"Day",
		False,
		"Nonconformance Report",
	),
	"rework_accept_pct": (
		"Rework accepted at verification (%)",
		rework_accept_pct,
		"Percent",
		False,
		"Nonconformance Report",
	),
	"rework_open_over_7_days": (
		"Rework open > 7 days (now)",
		rework_open_over_7_days,
		"Nos",
		True,
		"Nonconformance Report",
	),
	"nc_open_over_30_days": (
		"NCRs open > 30 days (now)",
		nc_open_over_30_days,
		"Nos",
		True,
		"Nonconformance Report",
	),
	"nc_by_source": (
		"NCRs opened, by source and disposition",
		nc_by_source,
		"Nos",
		False,
		"Nonconformance Report",
	),
	"nc_capa_pct": ("NCRs requiring a CAPA (%)", nc_capa_pct, "Percent", False, "Nonconformance Report"),
	"capa_opened": ("CAPAs opened", capa_opened, "Nos", False, "Nonconformance Report"),
	"capa_open": ("CAPAs open (now)", capa_open, "Nos", True, "Nonconformance Report"),
	"capa_overdue": (
		"CAPAs past a QM-128 due date (now)",
		capa_overdue,
		"Nos",
		True,
		"Nonconformance Report",
	),
	"capa_closed_on_time_pct": (
		"CAPAs closed by the closure due date (%)",
		capa_closed_on_time_pct,
		"Percent",
		False,
		"Nonconformance Report",
	),
	"capa_avg_days_to_close": (
		"Average days to close a CAPA",
		capa_avg_days_to_close,
		"Day",
		False,
		"Nonconformance Report",
	),
	"capa_effective_pct": (
		"CAPAs verified Effective (%)",
		capa_effective_pct,
		"Percent",
		False,
		"Nonconformance Report",
	),
	"asset_inspection_on_time_pct": (
		"Asset maintenance/inspections on time (%)",
		asset_inspection_on_time_pct,
		"Percent",
		False,
		"Asset Maintenance Log",
	),
	"assets_out_of_service": ("Assets Out of Service (now)", assets_out_of_service, "Nos", True, "Asset"),
	"hk_avg_score": (
		"Housekeeping average score (%)",
		hk_avg_score,
		"Percent",
		False,
		"Housekeeping Inspection",
	),
	"hk_areas_overdue": (
		"Housekeeping areas overdue (now)",
		hk_areas_overdue,
		"Nos",
		True,
		"Housekeeping Area",
	),
	"training_compliance_pct": (
		"Training compliance, required items Qualified (%) (now)",
		training_compliance_pct,
		"Percent",
		True,
		"Employee Training Matrix",
	),
	"training_overdue": (
		"Required training items overdue (now)",
		training_overdue,
		"Nos",
		True,
		"Employee Training Matrix",
	),
	"training_high_hazard_overdue": (
		"High-hazard training items overdue (now)",
		training_high_hazard_overdue,
		"Nos",
		True,
		"Employee Training Matrix",
	),
	"training_onboarding_on_time_pct": (
		"New-hire training completed by its deadline (%)",
		training_onboarding_on_time_pct,
		"Percent",
		False,
		"Employee Training Matrix",
	),
}


# Metrics that need the objective's QC Stage.
STAGE_METRICS = {"qc_stage_first_pass_yield"}


def stage_objective(stage: str) -> str:
	return _("First-pass yield: {0} (%)").format(stage)


def metric_options() -> str:
	return "\n" + "\n".join(METRICS)


def calculate(metric: str, start, end, stage: str | None = None):
	if metric not in METRICS:
		return None, _("Unknown metric {0}.").format(metric)
	_label, fn, _uom, snapshot, doctype = METRICS[metric]
	if metric in STAGE_METRICS and not stage:
		return None, _("Set the QC Stage on this objective.")
	if not _exists(doctype):
		return None, _("{0} is not installed on this site.").format(doctype)
	if metric in STAGE_METRICS:
		value, detail = fn(start, end, stage)
	else:
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
def get_metric_value(
	metric: str,
	period_start: str | None = None,
	period_end: str | None = None,
	stage: str | None = None,
) -> dict:
	"""For dashboards / Number Cards. Defaults to the previous calendar month."""
	frappe.only_for(("Quality Manager", "System Manager"))
	if not (period_start and period_end):
		period_start, period_end = get_review_period("Monthly", getdate())
	value, detail = calculate(metric, period_start, period_end, stage)
	return {
		"metric": metric,
		"value": value,
		"detail": detail,
		"period_start": period_start,
		"period_end": period_end,
	}
