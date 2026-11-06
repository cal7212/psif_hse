# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Read-only training queries shared by the Training Dashboard, the Executive Dashboard and the
quality metrics (TRN-700 Rev 1).

Row statuses come from the daily matrix refresh (status.py): a row is Due when its due date is
within 30 days and Overdue after it. "Coming due" here means a required row that is not
Overdue and whose due date falls within the chosen horizon.

A skill map is an employee's Employee Training Matrix Skill row: the skill, why it is needed
(Role, Target or Prerequisite) and its status. Its required training is the Skill Definition's
course list. A skill map is at risk when any of those courses is Overdue or coming due on that
employee's matrix, or when its authorization expires within the horizon.

Pass matrices=None to read every active matrix (metrics); the dashboards pass the names the
signed-in user can read.
"""

from collections import Counter, defaultdict

import frappe
from frappe.utils import add_days, date_diff, getdate

ETM = "Employee Training Matrix"
OVERDUE, DUE, COMPLETED = "Overdue", "Due", "Completed"
OPEN_STATUSES = ("Not Started", "In Progress", DUE)
AUTHORIZED = "Authorized"
HORIZONS = (30, 60, 90)
MATRIX_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"department",
	"percent_complete",
	"required_count",
	"compliant_count",
	"overdue_count",
	"due_count",
]


def readable_matrices() -> list[dict]:
	"""Active matrices the signed-in user can read."""
	return frappe.get_list(
		ETM,
		filters={"active": 1},
		fields=MATRIX_FIELDS,
		order_by="employee_name asc",
		limit_page_length=0,
	)


def _all_matrices() -> list[dict]:
	return frappe.get_all(
		ETM,
		filters={"active": 1},
		fields=MATRIX_FIELDS,
		limit_page_length=0,
	)


def _names(matrices) -> list[str]:
	return [m.name for m in (matrices if matrices is not None else _all_matrices())]


def required_rows(matrices=None, extra=None) -> list[dict]:
	names = _names(matrices)
	if not names:
		return []
	filters = {"parenttype": ETM, "parent": ["in", names], "active": 1, "is_required": 1}
	filters.update(extra or {})
	return frappe.get_all(
		"Employee Training Matrix Item",
		filters=filters,
		fields=[
			"parent",
			"employee",
			"employee_name",
			"department",
			"training_requirement",
			"course_title",
			"status",
			"qualification",
			"due_date",
			"high_hazard",
		],
		limit_page_length=0,
	)


def is_coming_due(row, today, horizon: int) -> bool:
	if row.status not in OPEN_STATUSES or not row.due_date:
		return False
	days = date_diff(row.due_date, today)
	return 0 <= days <= horizon


def coming_due_rows(matrices=None, horizon: int = 30) -> list[dict]:
	today = getdate()
	rows = required_rows(matrices, {"status": ["in", OPEN_STATUSES], "due_date": ["is", "set"]})
	out = [r for r in rows if is_coming_due(r, today, horizon)]
	for r in out:
		r.days = date_diff(r.due_date, today)
	return sorted(out, key=lambda r: (r.days, r.employee_name or "", r.training_requirement))


def overdue_rows(matrices=None) -> list[dict]:
	today = getdate()
	rows = required_rows(matrices, {"status": OVERDUE})
	for r in rows:
		r.days = date_diff(r.due_date, today) if r.due_date else None
	return rows


# --------------------------------------------------------------------------- skill maps
def skill_courses() -> dict[str, list[str]]:
	"""Skill -> required Training Requirements, from enabled Skill Definitions."""
	defs = frappe.get_all("Skill Definition", filters={"disabled": 0}, fields=["name", "skill"])
	courses = defaultdict(list)
	if not defs:
		return courses
	by_name = {d.name: d.skill or d.name for d in defs}
	for c in frappe.get_all(
		"Skill Definition Course",
		filters={"parenttype": "Skill Definition", "parent": ["in", list(by_name)]},
		fields=["parent", "training_requirement"],
		order_by="idx asc",
	):
		if c.training_requirement:
			courses[by_name[c.parent]].append(c.training_requirement)
	return courses


def skill_maps(matrices=None, horizon: int = 30) -> dict:
	"""Per-skill summary and the at-risk skill-map rows.

	Returns {"skills": [...], "rows": [...]} where each row is one course (or authorization)
	on one employee's skill map that is Overdue or coming due within the horizon.
	"""
	if matrices is None:
		matrices = _all_matrices()
	by_matrix = {m.name: m for m in matrices}
	if not by_matrix:
		return {"skills": [], "rows": []}
	today = getdate()
	maps = frappe.get_all(
		"Employee Training Matrix Skill",
		filters={"parenttype": ETM, "parent": ["in", list(by_matrix)]},
		fields=[
			"parent",
			"skill",
			"needed_for",
			"status",
			"progress",
			"authorized_on",
			"authorization_expires",
			"target_due",
		],
		limit_page_length=0,
	)
	courses = skill_courses()
	wanted = {c for cs in courses.values() for c in cs}
	items = defaultdict(dict)
	if maps and wanted:
		for it in frappe.get_all(
			"Employee Training Matrix Item",
			filters={
				"parenttype": ETM,
				"parent": ["in", list({m.parent for m in maps})],
				"training_requirement": ["in", list(wanted)],
				"active": 1,
			},
			fields=["parent", "training_requirement", "course_title", "status", "due_date"],
			limit_page_length=0,
		):
			items[it.parent][it.training_requirement] = it

	summary = defaultdict(lambda: Counter())
	at_risk = defaultdict(set)
	rows = []
	for sm in maps:
		m = by_matrix[sm.parent]
		s = summary[sm.skill]
		s["mapped"] += 1
		s[sm.status or "Not Started"] += 1
		base = {
			"matrix": sm.parent,
			"employee": m.employee,
			"employee_name": m.employee_name,
			"department": m.department,
			"skill": sm.skill,
			"needed_for": sm.needed_for,
			"skill_status": sm.status,
		}
		for course in courses.get(sm.skill, []):
			it = items[sm.parent].get(course)
			if not it:
				continue
			if it.status == OVERDUE:
				kind = "overdue"
			elif is_coming_due(it, today, horizon):
				kind = "coming_due"
			else:
				continue
			s[kind] += 1
			at_risk[sm.skill].add(sm.parent)
			rows.append(
				{
					**base,
					"kind": kind,
					"item": course,
					"title": it.course_title or course,
					"status": it.status,
					"due_date": str(it.due_date) if it.due_date else None,
					"days": date_diff(it.due_date, today) if it.due_date else None,
				}
			)
		if sm.status == AUTHORIZED and sm.authorization_expires:
			days = date_diff(sm.authorization_expires, today)
			if days <= horizon:
				s["expiring"] += 1
				at_risk[sm.skill].add(sm.parent)
				rows.append(
					{
						**base,
						"kind": "authorization",
						"item": None,
						"title": None,
						"status": "Authorization expires" if days >= 0 else "Authorization expired",
						"due_date": str(sm.authorization_expires),
						"days": days,
					}
				)

	order = {"overdue": 0, "authorization": 1, "coming_due": 2}
	rows.sort(key=lambda r: (order.get(r["kind"], 3), r["days"] if r["days"] is not None else 0, r["skill"]))
	skills = [
		{
			"skill": skill,
			"mapped": c["mapped"],
			"authorized": c[AUTHORIZED],
			"ready": c["Ready for Authorization"],
			"in_training": c["In Training"],
			"not_started": c["Not Started"],
			"lapsed": c["Lapsed"],
			"overdue": c["overdue"],
			"coming_due": c["coming_due"],
			"expiring": c["expiring"],
			"at_risk": len(at_risk[skill]),
			"courses": courses.get(skill, []),
		}
		for skill, c in sorted(summary.items())
	]
	return {"skills": skills, "rows": rows}


def skill_maps_at_risk(matrices=None, horizon: int = 30) -> list[tuple[str, str]]:
	"""Distinct (matrix, skill) pairs at risk."""
	return sorted({(r["matrix"], r["skill"]) for r in skill_maps(matrices, horizon)["rows"]})


def skill_authorizations_expiring(matrices=None, horizon: int = 60) -> list[dict]:
	"""Authorized skill maps whose authorization expires within the horizon (or has expired)."""
	if matrices is None:
		matrices = _all_matrices()
	by_matrix = {m.name: m for m in matrices}
	if not by_matrix:
		return []
	limit = add_days(getdate(), horizon)
	rows = frappe.get_all(
		"Employee Training Matrix Skill",
		filters={
			"parenttype": ETM,
			"parent": ["in", list(by_matrix)],
			"status": AUTHORIZED,
			"authorization_expires": ["between", ["2000-01-01", str(limit)]],
		},
		fields=["parent", "skill", "authorization_expires"],
		order_by="authorization_expires asc",
		limit_page_length=0,
	)
	for r in rows:
		r.employee_name = by_matrix[r.parent].employee_name
	return rows
