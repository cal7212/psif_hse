# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Executive Dashboard: the opening page. One summary card per pillar (Safety, Training,
Quality) with headline numbers and the top items needing attention, a metric scorecard and
goal status. Each pillar links to its own dashboard (HSE Dashboard, Training Dashboard,
Shop QC Home) for the detail.

Everything is filtered by the signed-in user's read permissions."""

import frappe
from frappe import _
from frappe.utils import getdate

from hse.hse.page.hse_home import hse_home as hh
from hse.shop_qc.page.shop_qc_home import shop_qc_home as qc
from hse.training_matrix.page.training_dashboard import training_dashboard as td

# Scorecard (keys from hse.quality_metrics.metrics.METRICS)
SCORECARD = [
	(
		"Safety",
		[
			"recordable_cases",
			"incident_actions_overdue",
			"asset_inspection_on_time_pct",
			"assets_out_of_service",
			"hk_avg_score",
			"hk_areas_overdue",
		],
	),
	(
		"Training",
		[
			"training_compliance_pct",
			"training_overdue",
			"training_high_hazard_overdue",
			"training_due_30",
			"skill_maps_at_risk",
			"skill_authorizations_expiring",
		],
	),
	(
		"Quality",
		[
			"hpu_first_pass_yield",
			"hpu_units_released",
			"rework_opened",
			"nc_opened",
			"capa_overdue",
			"capa_closed_on_time_pct",
		],
	),
]

SAFETY_ATTENTION = [
	hh.att_injury_open,
	hh.att_assets_out,
	hh.att_hk_overdue,
	hh.att_maintenance_late,
	hh.att_sds_review,
]

QUALITY_ATTENTION = [
	qc.att_hold,
	qc.att_flagged,
	qc.att_needs_reinspection,
	qc.att_ncr,
	lambda shop: hh.att_capa_overdue(),
	lambda shop: hh.att_scar_overdue(),
	qc.att_late,
	qc.att_rework,
	lambda shop: hh.att_calibration(),
	qc.att_ready,
]

LEVEL_ORDER = {"danger": 0, "warning": 1, "info": 2}


def _attention(fns, *args) -> list[dict]:
	items = [a for a in (hh._safe(fn, *args) for fn in fns) if a]
	return sorted(items, key=lambda a: LEVEL_ORDER.get(a["level"], 3))


def pillar_status(attention: list[dict]) -> str:
	"""Action needed if any red item, Watch if any amber item, otherwise On track."""
	levels = {a["level"] for a in attention}
	if "danger" in levels:
		return "action"
	if "warning" in levels:
		return "watch"
	return "ok"


@frappe.whitelist()
def get_dashboard(period: str = "this_month") -> dict:
	if period not in hh.PERIODS:
		period = "this_month"
	start, end = hh.period_bounds(period)
	safety_att = _attention(SAFETY_ATTENTION)
	quality_att = _attention(QUALITY_ATTENTION, None)
	training = hh._safe(td.pillar)
	return {
		"user": frappe.utils.get_fullname(frappe.session.user),
		"today": str(getdate()),
		"overdue_range": hh.overdue_range(),
		"period": {"key": period, "label": _(hh.PERIODS[period]), "start": str(start), "end": str(end)},
		"periods": [{"key": k, "label": _(v)} for k, v in hh.PERIODS.items()],
		"safety": {
			"summary": hh._safe(hh.safety_summary),
			"attention": safety_att,
			"status": pillar_status(safety_att),
		},
		"training": training
		and {
			"summary": training["summary"],
			"attention": training["attention"],
			"status": pillar_status(training["attention"]),
		},
		"quality": {
			"pipeline": hh._safe(qc.pipeline, None, start, end),
			"attention": quality_att,
			"status": pillar_status(quality_att),
		},
		"metrics": hh._safe(hh.metric_groups, start, end, SCORECARD) or [],
		"reviews": hh._safe(hh.latest_reviews) or [],
	}
