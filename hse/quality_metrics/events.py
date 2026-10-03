# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cstr, now_datetime, nowdate

from hse.quality_metrics.metrics import (
	FAILED,
	METRICS,
	RECORD_ONLY,
	calculate,
	evaluate,
	get_review_period,
	target_text,
)

METRIC_FIELDS = ("hse_metric", "target_operator", "target_value")


# ---------------------------------------------------------------- Quality Goal
def quality_goal_validate(doc, method=None):
	for row in doc.objectives:
		if not row.get("hse_metric"):
			continue
		label, _fn, default_uom, _snap, _dt = METRICS.get(row.hse_metric, (None,) * 5)
		if not label:
			frappe.throw(_("Row {0}: unknown metric {1}.").format(row.idx, row.hse_metric))
		if not row.target_operator:
			row.target_operator = RECORD_ONLY
		if not row.objective:
			row.objective = label
		if not row.uom and default_uom and frappe.db.exists("UOM", default_uom):
			row.uom = default_uom
		row.target = target_text(row.target_operator, row.target_value, row.uom)


# ---------------------------------------------------------------- Quality Review
def quality_review_validate(doc, method=None):
	"""Runs after ERPNext's QualityReview.validate (which copies objectives from the goal)."""
	goal = frappe.get_doc("Quality Goal", doc.goal)
	if not (doc.get("period_start") and doc.get("period_end")):
		doc.period_start, doc.period_end = get_review_period(goal.frequency, doc.date or nowdate())

	by_objective = {cstr(o.objective).strip(): o for o in goal.objectives}
	for row in doc.reviews:
		if row.get("hse_metric"):
			continue
		src = by_objective.get(cstr(row.objective).strip())
		if src and src.get("hse_metric"):
			for f in METRIC_FIELDS:
				row.set(f, src.get(f))

	if doc.is_new() or doc.flags.recalculate_metrics:
		calculate_review(doc)
	doc.set_status()


def calculate_review(doc):
	for row in doc.reviews:
		if not row.get("hse_metric"):
			continue
		value, detail = calculate(row.hse_metric, doc.period_start, doc.period_end)
		row.actual_value = value
		row.metric_detail = detail
		row.status = evaluate(value, row.target_operator, row.target_value)
	doc.metrics_calculated_on = now_datetime()


def quality_review_on_update(doc, method=None):
	"""A failed review gets one Corrective Quality Action listing the failed objectives."""
	if doc.status != FAILED or frappe.db.exists("Quality Action", {"review": doc.name}):
		return
	failed = [r for r in doc.reviews if r.status == FAILED]
	goal_procedure = frappe.db.get_value("Quality Goal", doc.goal, "procedure")
	action = frappe.get_doc(
		{
			"doctype": "Quality Action",
			"corrective_preventive": "Corrective",
			"goal": doc.goal,
			"review": doc.name,
			"procedure": doc.procedure or goal_procedure,
			"date": nowdate(),
			"status": "Open",
			"resolutions": [
				{
					"problem": _("{0}: actual {1} against target {2} ({3} to {4}). {5}").format(
						cstr(r.objective),
						"" if r.get("actual_value") is None else r.actual_value,
						cstr(r.target),
						doc.period_start,
						doc.period_end,
						cstr(r.get("metric_detail")),
					),
					"status": "Open",
				}
				for r in failed
			],
		}
	)
	action.flags.ignore_permissions = True
	action.insert()
	frappe.msgprint(
		_("Quality Review failed. Quality Action {0} created for {1} objective(s).").format(
			frappe.get_desk_link("Quality Action", action.name), len(failed)
		),
		indicator="red",
		alert=True,
	)


# ---------------------------------------------------------------- Non Conformance
def non_conformance_validate(doc, method=None):
	"""Stamp the resolution time so 'days to resolve' can be measured."""
	if doc.status == "Resolved":
		if not doc.get("resolved_on"):
			doc.resolved_on = now_datetime()
	elif doc.get("resolved_on"):
		doc.resolved_on = None


# ---------------------------------------------------------------- API
@frappe.whitelist(methods=["POST"])
def recalculate_review(review: str) -> dict:
	doc = frappe.get_doc("Quality Review", review)
	doc.check_permission("write")
	doc.flags.recalculate_metrics = True
	doc.save()
	return doc.as_dict()


@frappe.whitelist()
def get_metric_choices() -> list[dict]:
	return [
		{"value": key, "label": label, "uom": uom, "snapshot": snap}
		for key, (label, _fn, uom, snap, _dt) in METRICS.items()
	]


@frappe.whitelist(methods=["POST"])
def create_starter_goals() -> dict:
	"""Desk button on the Quality Goal list. Same as the bench command."""
	frappe.only_for(("Quality Manager", "System Manager"))
	from hse.quality_metrics.install import create_starter_goals as _create
	from hse.quality_metrics.starter_goals import STARTER_GOALS

	created = _create()
	existing = [g["goal"] for g in STARTER_GOALS if g["goal"] not in created]
	return {"created": created, "existing": existing}


@frappe.whitelist()
def get_missing_starter_goals() -> list[str]:
	from hse.quality_metrics.starter_goals import STARTER_GOALS

	return [g["goal"] for g in STARTER_GOALS if not frappe.db.exists("Quality Goal", g["goal"])]
