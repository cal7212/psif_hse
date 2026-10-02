# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from hse.quality_metrics.metrics import METRICS, OPERATORS, metric_options
from hse.quality_metrics.starter_goals import STARTER_GOALS

MODULE = "Quality Metrics"


def get_custom_fields():
	operator_options = "\n" + "\n".join(OPERATORS)
	return {
		"Quality Goal Objective": [
			{
				"fieldname": "hse_metric",
				"label": "Calculated Metric",
				"fieldtype": "Select",
				"options": metric_options(),
				"insert_after": "uom",
				"in_list_view": 1,
				"columns": 2,
				"description": "Leave blank for a manually reviewed objective.",
			},
			{
				"fieldname": "target_operator",
				"label": "Target Is",
				"fieldtype": "Select",
				"options": operator_options,
				"insert_after": "hse_metric",
				"depends_on": "hse_metric",
				"in_list_view": 1,
				"columns": 1,
			},
			{
				"fieldname": "target_value",
				"label": "Target Value",
				"fieldtype": "Float",
				"insert_after": "target_operator",
				"depends_on": "eval:doc.hse_metric && doc.target_operator != 'Record only'",
				"in_list_view": 1,
				"columns": 1,
			},
		],
		"Quality Review Objective": [
			{
				"fieldname": "hse_metric",
				"label": "Calculated Metric",
				"fieldtype": "Select",
				"options": metric_options(),
				"insert_after": "uom",
				"read_only": 1,
			},
			{
				"fieldname": "target_operator",
				"label": "Target Is",
				"fieldtype": "Data",
				"insert_after": "hse_metric",
				"read_only": 1,
				"hidden": 1,
			},
			{
				"fieldname": "target_value",
				"label": "Target Value",
				"fieldtype": "Float",
				"insert_after": "target_operator",
				"read_only": 1,
				"hidden": 1,
			},
			{
				"fieldname": "actual_value",
				"label": "Actual",
				"fieldtype": "Float",
				"insert_after": "target_value",
				"read_only": 1,
				"in_list_view": 1,
				"columns": 1,
				"depends_on": "hse_metric",
			},
			{
				"fieldname": "metric_detail",
				"label": "Calculation Detail",
				"fieldtype": "Small Text",
				"insert_after": "actual_value",
				"read_only": 1,
				"depends_on": "hse_metric",
			},
		],
		"Quality Review": [
			{
				"fieldname": "period_start",
				"label": "Period Start",
				"fieldtype": "Date",
				"insert_after": "date",
				"description": "Defaults to the last complete period for the goal's frequency.",
			},
			{
				"fieldname": "period_end",
				"label": "Period End",
				"fieldtype": "Date",
				"insert_after": "period_start",
			},
			{
				"fieldname": "metrics_calculated_on",
				"label": "Metrics Calculated On",
				"fieldtype": "Datetime",
				"insert_after": "period_end",
				"read_only": 1,
				"no_copy": 1,
			},
		],
		"Non Conformance": [
			{
				"fieldname": "resolved_on",
				"label": "Resolved On",
				"fieldtype": "Datetime",
				"insert_after": "status",
				"read_only": 1,
				"no_copy": 1,
				"depends_on": "eval:doc.status=='Resolved'",
			},
		],
	}


def make_custom_fields():
	fields = get_custom_fields()
	for rows in fields.values():
		for row in rows:
			row["module"] = MODULE
	create_custom_fields(fields, update=True)


def backfill_resolved_on():
	"""Existing resolved NCs: use last-modified time as the best available resolution time."""
	nc = frappe.qb.DocType("Non Conformance")
	(
		frappe.qb.update(nc)
		.set(nc.resolved_on, nc.modified)
		.where((nc.status == "Resolved") & nc.resolved_on.isnull())
		.run()
	)


def create_starter_goals(frequency: str = "Monthly", day_of_month: str = "1") -> list[str]:
	"""Run once by hand:
	bench --site <site> execute hse.quality_metrics.install.create_starter_goals
	Goals whose module isn't in use are still created; delete any you don't need.
	Existing goals with the same name are left alone."""
	created = []
	for spec in STARTER_GOALS:
		if frappe.db.exists("Quality Goal", spec["goal"]):
			continue
		goal = frappe.get_doc(
			{
				"doctype": "Quality Goal",
				"goal": spec["goal"],
				"frequency": frequency,
				"date": day_of_month if frequency == "Monthly" else None,
				"objectives": [
					{"objective": METRICS[key][0], "hse_metric": key, "target_operator": op, "target_value": val}
					for key, op, val in spec["objectives"]
				],
			}
		)
		goal.insert(ignore_permissions=True)
		created.append(goal.name)
	return created


def after_install():
	after_migrate()


def after_migrate():
	make_custom_fields()
	backfill_resolved_on()
