# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Training Dashboard: the Training pillar page (TRN-700 Rev 1).

Headline strip, items needing attention, required training coming due, skill maps with
required training overdue or coming due, overdue by course and department, employees most
behind, training metrics and goals. Matrix data is limited to the matrices the signed-in user
can read; the metrics (which cover every active matrix) only show to users who can read the
Employee Training Matrix doctype."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, getdate

from hse.hse.page.hse_home.hse_home import (
	PERIODS,
	_can,
	_count,
	_item,
	_safe,
	latest_reviews,
	metric_groups,
	overdue_range,
	period_bounds,
)
from hse.quality_metrics.metrics import METRICS
from hse.training_matrix import dashboard_data as dd

ETM = dd.ETM

METRIC_GROUPS = [
	(
		"Compliance",
		[
			"training_compliance_pct",
			"training_overdue",
			"training_high_hazard_overdue",
			"training_employees_overdue",
			"training_due_30",
			"training_onboarding_on_time_pct",
		],
	),
	("Skills", ["skill_maps_at_risk", "skill_authorizations_expiring"]),
]

LEVEL_ORDER = {"danger": 0, "warning": 1, "info": 2}
DASHBOARD_ROUTE = "/app/training-dashboard"


@frappe.whitelist()
def get_dashboard(period: str = "this_month", horizon: int = 30) -> dict:
	if period not in PERIODS:
		period = "this_month"
	horizon = cint(horizon)
	if horizon not in dd.HORIZONS:
		horizon = 30
	start, end = period_bounds(period)
	ctx = _safe(context, horizon)
	return {
		"user": frappe.utils.get_fullname(frappe.session.user),
		"today": str(getdate()),
		"overdue_range": overdue_range(),
		"period": {"key": period, "label": _(PERIODS[period]), "start": str(start), "end": str(end)},
		"periods": [{"key": k, "label": _(v)} for k, v in PERIODS.items()],
		"horizon": horizon,
		"horizons": list(dd.HORIZONS),
		"can_read": bool(ctx),
		"headline": (ctx or {}).get("headline", []),
		"attention": attention(ctx),
		"coming_due": (ctx or {}).get("coming_due", [])[:15],
		"coming_due_total": len((ctx or {}).get("coming_due", [])),
		"skills": (ctx or {}).get("skills") or {"skills": [], "rows": []},
		"by_course": (ctx or {}).get("by_course", []),
		"by_department": (ctx or {}).get("by_department", []),
		"employees": (ctx or {}).get("employees", []),
		"metrics": _safe(metric_groups, start, end, METRIC_GROUPS) or [],
		"reviews": _safe(latest_reviews, training_goals()) or [],
	}


def _employees(n: int) -> str:
	return _("1 employee") if n == 1 else _("{0} employees").format(n)


# --------------------------------------------------------------------------- data
def context(horizon: int = 30) -> dict | None:
	"""Everything computed from the matrices the user can read, gathered once."""
	if not _can(ETM):
		return None
	matrices = dd.readable_matrices()
	rows = dd.required_rows(matrices)
	overdue = [r for r in rows if r.status == dd.OVERDUE]
	coming = dd.coming_due_rows(matrices, horizon)
	skills = dd.skill_maps(matrices, horizon)
	qualified = sum(1 for r in rows if r.qualification == "Qualified")
	hh_overdue = [r for r in overdue if r.high_hazard]
	at_risk = {(r["matrix"], r["skill"]) for r in skills["rows"]}
	return {
		"matrices": matrices,
		"overdue": overdue,
		"high_hazard": hh_overdue,
		"coming_due": [_due_row(r) for r in coming],
		"skills": skills,
		"at_risk": at_risk,
		"by_course": by_course(overdue, coming),
		"by_department": by_department(rows),
		"employees": employees_behind(matrices),
		"headline": [
			_step(
				"training_compliance_pct",
				_("Required items Qualified"),
				round(qualified / len(rows) * 100, 1) if rows else None,
				"good" if rows and qualified == len(rows) else "bad",
				_("{0} of {1} required items").format(qualified, len(rows)),
			),
			_step(
				"training_overdue",
				_("Required items overdue"),
				len(overdue),
				"bad",
				_employees(len({r.parent for r in overdue})),
			),
			_step(
				"training_high_hazard_overdue",
				_("High-hazard overdue"),
				len(hh_overdue),
				"bad",
			),
			_step(
				"training_due",
				_("Coming due in {0} days").format(horizon),
				len(coming),
				"warn",
			),
			_step(
				"skill_maps_at_risk",
				_("Skill maps at risk"),
				len(at_risk),
				"warn",
				_("Required courses overdue or coming due"),
			),
			_step(
				"employees",
				_("Employees with overdue training"),
				len({r.parent for r in overdue}),
				"bad",
				_("of {0} active").format(len(matrices)),
			),
		],
	}


def _step(key, label, value, tone, detail=None):
	return {"key": key, "label": label, "value": value, "tone": tone, "detail": detail}


def _due_row(r) -> dict:
	return {
		"matrix": r.parent,
		"employee_name": r.employee_name,
		"department": r.department,
		"item": r.training_requirement,
		"title": r.course_title or r.training_requirement,
		"status": r.status,
		"due_date": str(r.due_date) if r.due_date else None,
		"days": r.days,
		"high_hazard": r.high_hazard,
	}


def by_course(overdue, coming, limit: int = 8) -> list[dict]:
	counts = defaultdict(lambda: {"overdue": 0, "coming_due": 0, "title": None})
	for r in overdue:
		c = counts[r.training_requirement]
		c["overdue"] += 1
		c["title"] = c["title"] or r.course_title
	for r in coming:
		c = counts[r.training_requirement]
		c["coming_due"] += 1
		c["title"] = c["title"] or r.course_title
	out = [
		{"item": k, "title": v["title"] or k, "overdue": v["overdue"], "coming_due": v["coming_due"]}
		for k, v in counts.items()
	]
	out.sort(key=lambda x: (-x["overdue"], -x["coming_due"], x["item"]))
	return out[:limit]


def by_department(rows) -> list[dict]:
	dept = defaultdict(lambda: {"required": 0, "qualified": 0, "overdue": 0})
	for r in rows:
		d = dept[r.department or ""]
		d["required"] += 1
		d["qualified"] += r.qualification == "Qualified"
		d["overdue"] += r.status == dd.OVERDUE
	out = [
		{
			"department": k or None,
			"required": v["required"],
			"qualified": v["qualified"],
			"overdue": v["overdue"],
			"pct": round(v["qualified"] / v["required"] * 100, 1) if v["required"] else None,
		}
		for k, v in dept.items()
	]
	out.sort(key=lambda x: (x["pct"] if x["pct"] is not None else 101, x["department"] or ""))
	return out


def employees_behind(matrices, limit: int = 10) -> list[dict]:
	behind = [m for m in matrices if m.overdue_count or m.due_count]
	behind.sort(key=lambda m: (-(m.overdue_count or 0), -(m.due_count or 0), m.employee_name or ""))
	return [
		{
			"matrix": m.name,
			"employee_name": m.employee_name,
			"department": m.department,
			"percent_complete": m.percent_complete,
			"overdue": m.overdue_count or 0,
			"due": m.due_count or 0,
			"required": m.required_count or 0,
		}
		for m in behind[:limit]
	]


# --------------------------------------------------------------------------- attention
def attention(ctx) -> list[dict]:
	items = []
	if ctx:
		hh_n = len(ctx["high_hazard"])
		items.append(
			_item(
				"high_hazard",
				_("High-hazard training overdue"),
				hh_n,
				ETM,
				None,
				"danger",
				_employees(len({r.parent for r in ctx["high_hazard"]})),
			)
		)
		items.append(
			_item(
				"overdue",
				_("Required training overdue"),
				len(ctx["overdue"]),
				ETM,
				{"overdue_count": [">", 0]},
				"warning",
				_employees(len({r.parent for r in ctx["overdue"]})),
			)
		)
		rows = ctx["skills"]["rows"]
		expiring = [r for r in rows if r["kind"] == "authorization"]
		items.append(
			_item(
				"skills",
				_("Skill maps with required training overdue or coming due"),
				len(ctx["at_risk"]),
				ETM,
				None,
				"warning",
				", ".join(sorted({r["skill"] for r in rows})[:4]) or None,
				route=DASHBOARD_ROUTE,
			)
		)
		items.append(
			_item(
				"auth_expiring",
				_("Skill authorizations expiring"),
				len(expiring),
				ETM,
				None,
				"warning",
				route=DASHBOARD_ROUTE,
			)
		)
		items.append(
			_item(
				"due",
				_("Required training coming due"),
				len(ctx["coming_due"]),
				ETM,
				None,
				"info",
				route=DASHBOARD_ROUTE,
			)
		)
	for fn in (att_ready_for_authorization, att_requests, att_materials_review, att_confirm):
		items.append(_safe(fn))
	items = [a for a in items if a]
	items.sort(key=lambda a: LEVEL_ORDER.get(a["level"], 3))
	return items


def att_ready_for_authorization():
	if not _can(ETM):
		return None
	names = [m.name for m in dd.readable_matrices()]
	if not names:
		return None
	n = len(
		frappe.get_all(
			"Employee Training Matrix Skill",
			filters={"parenttype": ETM, "parent": ["in", names], "status": "Ready for Authorization"},
			pluck="name",
		)
	)
	return _item("ready", _("Skills ready for authorization"), n, ETM, None, "info")


def att_requests():
	if not _can("Training Request"):
		return None
	f = {"status": "Pending"}
	return _item(
		"requests",
		_("Training requests to decide"),
		_count("Training Request", f),
		"Training Request",
		f,
		"info",
	)


def att_materials_review():
	if not _can("Training Requirement"):
		return None
	f = {"disabled": 0, "materials_review_due": ["between", ["2000-01-01", str(getdate())]]}
	return _item(
		"materials",
		_("Course materials review due"),
		_count("Training Requirement", f),
		"Training Requirement",
		f,
		"info",
	)


def att_confirm():
	if not _can(ETM):
		return None
	f = {"confirm_count": [">", 0], "active": 1}
	return _item(
		"confirm",
		_("Matrices with conditional training to confirm"),
		_count(ETM, f),
		ETM,
		f,
		"info",
	)


def training_goals() -> list[str]:
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


def pillar() -> dict | None:
	"""Training pillar card on the Executive Dashboard: headline numbers and attention."""
	ctx = context(30)
	if not ctx:
		return None
	return {
		"summary": {s["key"]: s["value"] for s in ctx["headline"]},
		"attention": attention(ctx),
	}
