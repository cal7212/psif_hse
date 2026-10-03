# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Shared OSHA 300 / 300A logic built from Injury_Illness Report (29 CFR 1904)."""

import frappe
from frappe import _

DAY_CAP = 180  # 1904.7(b)(3)(vii)

# Column M categories, in form order
ILLNESS_TYPES = [
	("Injury", "injury"),
	("Skin Disorder", "skin_disorder"),
	("Respiratory Condition", "respiratory"),
	("Poisoning", "poisoning"),
	("Hearing Loss", "hearing_loss"),
	("All other Illnesses", "other_illness"),
]

# Columns G-J: only the most serious outcome is checked.
# Labels are translated where used, not at import (Frappe multitenancy rule).
OUTCOMES = [
	("death", "Death"),
	("days_away", "Days Away"),
	("transfer", "Job Transfer or Restriction"),
	("other", "Other Recordable"),
]


def get_cases(year: int, include_drafts: bool = False) -> list[dict]:
	"""Recordable cases for a calendar year, one dict per OSHA 300 line."""
	docstatus = ["in", [0, 1]] if include_drafts else 1
	reports = frappe.get_all(
		"Injury_Illness Report",
		filters={
			"is_recordable": 1,
			"docstatus": docstatus,
			"incident_date": ["between", [f"{year}-01-01", f"{year}-12-31"]],
		},
		fields=[
			"name",
			"docstatus",
			"employee_name",
			"non_employee_name",
			"privacy_case",
			"incident_date",
			"incident_location",
			"injury_type",
			"body_part_affected",
			"object_harm",
			"classification",
			"death_date",
		],
		order_by="incident_date asc, name asc",
	)
	if not reports:
		return []

	names = [r.name for r in reports]
	days = {}
	for row in frappe.get_all(
		"Days Away from Work",
		filters={"parenttype": "Injury_Illness Report", "parent": ["in", names]},
		fields=["parent", "parentfield", "number_of_days_away"],
	):
		key = (row.parent, row.parentfield)
		days[key] = days.get(key, 0) + (row.number_of_days_away or 0)

	employees = {
		e.name: e
		for e in frappe.get_all(
			"Employee",
			filters={"name": ["in", [r.employee_name for r in reports if r.employee_name]]},
			fields=["name", "employee_name", "designation"],
		)
	}

	cases = []
	for r in reports:
		emp = employees.get(r.employee_name)
		away = min(days.get((r.name, "days_away"), 0), DAY_CAP)
		restricted = min(days.get((r.name, "job_restriction"), 0), DAY_CAP)
		if r.death_date:
			outcome = "death"
		elif away > 0:
			outcome = "days_away"
		elif restricted > 0:
			outcome = "transfer"
		else:
			outcome = "other"

		type_key = dict(ILLNESS_TYPES).get(r.classification)
		description = ", ".join(x for x in (r.injury_type, r.body_part_affected) if x)
		if r.object_harm:
			description = f"{description}; {r.object_harm}" if description else r.object_harm

		cases.append(
			frappe._dict(
				case_no=r.name,
				draft=r.docstatus == 0,
				employee=_("Privacy Case")
				if r.privacy_case
				else (emp.employee_name if emp else (r.non_employee_name or r.employee_name or "")),
				job_title=(emp.designation if emp else "") or "",
				incident_date=r.incident_date,
				location=r.incident_location or "",
				description=description,
				outcome=outcome,
				outcome_label=_(dict(OUTCOMES)[outcome]),
				days_away=away,
				days_restricted=restricted,
				illness_type=r.classification if type_key else "",
				illness_key=type_key,
			)
		)
	return cases


def summarize(cases: list[dict]) -> frappe._dict:
	"""Column totals for the OSHA 300A."""
	totals = frappe._dict(
		total_deaths=0,
		total_days_away_cases=0,
		total_transfer_cases=0,
		total_other_cases=0,
		total_days_away=0,
		total_transfer_days=0,
		cases_missing_type=0,
	)
	for _label, key in ILLNESS_TYPES:
		totals[f"total_{key}"] = 0
	outcome_field = {
		"death": "total_deaths",
		"days_away": "total_days_away_cases",
		"transfer": "total_transfer_cases",
		"other": "total_other_cases",
	}
	for c in cases:
		totals[outcome_field[c.outcome]] += 1
		totals.total_days_away += c.days_away
		totals.total_transfer_days += c.days_restricted
		if c.illness_key:
			totals[f"total_{c.illness_key}"] += 1
		else:
			totals.cases_missing_type += 1
	return totals


def incidence_rate(cases: int, hours: float) -> float:
	"""Cases per 100 full-time workers: cases x 200,000 / hours worked."""
	return round(cases * 200000 / hours, 2) if hours else 0.0
