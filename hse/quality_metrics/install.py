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
			{
				"fieldname": "qc_stage",
				"label": "QC Stage",
				"fieldtype": "Link",
				"options": "QC Stage",
				"insert_after": "target_value",
				"depends_on": "eval:doc.hse_metric == 'qc_stage_first_pass_yield'",
				"mandatory_depends_on": "eval:doc.hse_metric == 'qc_stage_first_pass_yield'",
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
				"fieldname": "qc_stage",
				"label": "QC Stage",
				"fieldtype": "Link",
				"options": "QC Stage",
				"insert_after": "target_value",
				"read_only": 1,
				"depends_on": "qc_stage",
			},
			{
				"fieldname": "actual_value",
				"label": "Actual",
				"fieldtype": "Float",
				"insert_after": "qc_stage",
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
	}


def make_custom_fields():
	fields = get_custom_fields()
	for rows in fields.values():
		for row in rows:
			row["module"] = MODULE
	create_custom_fields(fields, update=True)


def create_starter_goals(
	frequency: str = "Monthly", day_of_month: str = "1", goals: list[str] | None = None
) -> list[str]:
	"""Run from the "Create Starter Goals" button on the Quality Goal list, or by hand:
	bench --site <site> execute hse.quality_metrics.install.create_starter_goals
	Goals whose module isn't in use are still created; delete any you don't need.
	Existing goals with the same name are left alone."""
	created = []
	for spec in STARTER_GOALS:
		if goals and spec["goal"] not in goals:
			continue
		if frappe.db.exists("Quality Goal", spec["goal"]):
			continue
		goal = frappe.get_doc(
			{
				"doctype": "Quality Goal",
				"goal": spec["goal"],
				"frequency": frequency,
				"date": day_of_month if frequency == "Monthly" else None,
				"objectives": [
					{
						"objective": METRICS[key][0],
						"hse_metric": key,
						"target_operator": op,
						"target_value": val,
					}
					for key, op, val in spec["objectives"]
				],
			}
		)
		goal.insert(ignore_permissions=True)
		created.append(goal.name)
	return created


STAGE_FPY_GOAL_PREFIX = "First Pass Yield by Stage"


def stage_group(stage) -> str:
	if stage.shop:
		return stage.shop
	return "Repair" if stage.job_type == "Repair" else "General"


def create_stage_fpy_goals(
	target: float | None = None, frequency: str = "Monthly", day_of_month: str = "1"
) -> dict:
	"""One Quality Goal per shop with a first-pass-yield objective for each enabled QC Stage.
	No target -> Record only. Existing goals get rows for stages they do not have yet."""
	from hse.quality_metrics.metrics import AT_LEAST, RECORD_ONLY, stage_objective

	stages = frappe.get_all(
		"QC Stage",
		filters={"disabled": 0},
		fields=["name", "shop", "job_type", "sequence"],
		order_by="sequence asc, name asc",
	)
	groups: dict[str, list] = {}
	for st in stages:
		groups.setdefault(stage_group(st), []).append(st)

	operator = RECORD_ONLY if target in (None, "") else AT_LEAST
	created, updated = [], []
	for group, rows in sorted(groups.items()):
		name = f"{STAGE_FPY_GOAL_PREFIX} - {group}"

		def objective(st):
			return {
				"objective": stage_objective(st.name),
				"hse_metric": "qc_stage_first_pass_yield",
				"qc_stage": st.name,
				"target_operator": operator,
				"target_value": target or 0,
			}

		if frappe.db.exists("Quality Goal", name):
			goal = frappe.get_doc("Quality Goal", name)
			have = {o.get("qc_stage") for o in goal.objectives}
			missing = [st for st in rows if st.name not in have]
			if missing:
				for st in missing:
					goal.append("objectives", objective(st))
				goal.save(ignore_permissions=True)
				updated.append(name)
			continue
		goal = frappe.get_doc(
			{
				"doctype": "Quality Goal",
				"goal": name,
				"frequency": frequency,
				"date": day_of_month if frequency == "Monthly" else None,
				"objectives": [objective(st) for st in rows],
			}
		)
		goal.insert(ignore_permissions=True)
		created.append(name)
	return {"created": created, "updated": updated}


def after_install():
	after_migrate()


def after_migrate():
	make_custom_fields()
