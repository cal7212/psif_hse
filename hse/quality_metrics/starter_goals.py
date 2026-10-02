# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Starter Quality Goals. Targets are examples; set your own before relying on them."""

STARTER_GOALS = [
	{
		"goal": "HPU Build Quality",
		"objectives": [
			("hpu_first_pass_yield", "At least", 90),
			("hpu_shipped_before_release", "At most", 0),
			("hpu_units_released", "Record only", 0),
			("hpu_stage_rejections", "Record only", 0),
		],
	},
	{
		"goal": "Non Conformance Management",
		"objectives": [
			("nc_avg_days_to_resolve", "At most", 14),
			("nc_open_critical_over_7_days", "At most", 0),
			("nc_opened", "Record only", 0),
		],
	},
	{
		"goal": "Equipment Inspections",
		"objectives": [
			("asset_inspection_on_time_pct", "At least", 95),
			("assets_out_of_service", "Record only", 0),
		],
	},
	{
		"goal": "Housekeeping",
		"objectives": [
			("hk_avg_score", "At least", 85),
			("hk_areas_overdue", "At most", 0),
		],
	},
]
