# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Starter Quality Goals. Targets are examples; set your own before relying on them."""

STARTER_GOALS = [
	{
		"goal": "Shop QC Quality",
		"objectives": [
			("hpu_first_pass_yield", "At least", 90),
			("hpu_shipped_before_release", "At most", 0),
			("hpu_units_released", "Record only", 0),
			("hpu_stage_rejections", "Record only", 0),
			("unit_on_time_delivery_pct", "At least", 95),
		],
	},
	{
		"goal": "Repairs and RGAs",
		"objectives": [
			("rga_received", "Record only", 0),
			("repair_turnaround_days", "Record only", 0),
			("repair_failure_causes", "Record only", 0),
		],
	},
	# Rework / NCR / CAPA goals mostly record values; the QM-400 Appendix C KPIs carry its targets.
	{
		"goal": "Rework Management",
		"objectives": [
			("rework_opened", "Record only", 0),
			("rework_escalation_pct", "Record only", 0),
			("rework_accept_pct", "Record only", 0),
			("rework_avg_days_to_close", "Record only", 0),
			("rework_open_over_7_days", "Record only", 0),
		],
	},
	{
		"goal": "NCR Management",
		"objectives": [
			("nc_opened", "Record only", 0),
			("nc_by_source", "Record only", 0),
			("nc_capa_pct", "Record only", 0),
			("nc_avg_days_to_resolve", "Record only", 0),
			("nc_open_critical_over_7_days", "Record only", 0),
			("nc_open_over_30_days", "Record only", 0),
			("nc_closed_on_time_pct", "At least", 90),
			("complaint_ack_on_time_pct", "At least", 100),
		],
	},
	{
		"goal": "CAPA Management",
		"objectives": [
			("capa_opened", "Record only", 0),
			("capa_open", "Record only", 0),
			("capa_overdue", "Record only", 0),
			("capa_closed_on_time_pct", "Record only", 0),
			("capa_avg_days_to_close", "Record only", 0),
			("capa_effective_pct", "At least", 90),
		],
	},
	{
		"goal": "Calibration",
		"objectives": [
			("calibration_compliance_pct", "At least", 100),
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
	{
		"goal": "Training and Competency",
		"objectives": [
			("training_compliance_pct", "At least", 95),
			("training_high_hazard_overdue", "At most", 0),
			("training_onboarding_on_time_pct", "At least", 95),
			("training_overdue", "Record only", 0),
		],
	},
]
