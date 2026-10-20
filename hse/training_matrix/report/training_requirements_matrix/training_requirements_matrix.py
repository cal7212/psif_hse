# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""TRN-701 Part 1: Training Requirements Matrix by role (TRN-700 Rev 1 Appendix A).

R = required for the role, C = conditional (required if the task or hazard applies), — = not applicable.
Courses a role needs through a skill (Skill Definition) are included. Three total rows close the
report: required hours and conditional hours per role, and how many of those courses have no
duration yet, so a total is never silently short.
"""

import frappe
from frappe import _

from hse.training_matrix import skill_status as ss
from hse.training_matrix import skills as sk
from hse.training_matrix.status import CONDITIONAL, NOT_REQUIRED, REQUIRED

AVENUE_ORDER = {"HR Onboarding": 0, "Safety / EHS": 1, "QMS": 2, "Technical": 3}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	roles = frappe.get_all("Training Role", filters={"disabled": 0}, pluck="name", order_by="creation asc")
	conditions = {} if filters.get("include_disabled") else {"disabled": 0}
	if filters.get("avenue"):
		conditions["avenue"] = filters.avenue
	reqs = frappe.get_list(
		"Training Requirement",
		filters=conditions,
		fields=[
			"name",
			"course_title",
			"avenue",
			"delivery_method",
			"frequency_summary",
			"verification_method",
			"all_employees",
			"high_hazard",
			"duration_minutes",
		],
		limit_page_length=0,
	)
	codes = {}
	for r in frappe.get_all(
		"Training Requirement Role",
		filters={"parenttype": "Training Requirement", "parent": ["in", [x.name for x in reqs] or [""]]},
		fields=["parent", "training_role", "requirement_code"],
	):
		codes[(r.parent, r.training_role)] = r.requirement_code
	add_skill_courses(codes, roles)

	columns = [
		{
			"label": _("Course ID"),
			"fieldname": "course",
			"fieldtype": "Link",
			"options": "Training Requirement",
			"width": 120,
		},
		{"label": _("Training Topic"), "fieldname": "course_title", "fieldtype": "Data", "width": 260},
		{"label": _("Avenue"), "fieldname": "avenue", "fieldtype": "Data", "width": 110},
		{"label": _("Delivery Method"), "fieldname": "delivery_method", "fieldtype": "Data", "width": 130},
		{"label": _("Frequency"), "fieldname": "frequency_summary", "fieldtype": "Data", "width": 200},
		{
			"label": _("Competency Verification"),
			"fieldname": "verification_method",
			"fieldtype": "Data",
			"width": 160,
		},
	]
	columns += [
		{"label": role, "fieldname": "r_" + frappe.scrub(role), "fieldtype": "Data", "width": 90}
		for role in roles
	]
	columns += [{"label": _("Minutes"), "fieldname": "duration_minutes", "fieldtype": "Int", "width": 75}]

	data = []
	for req in sorted(reqs, key=lambda x: (AVENUE_ORDER.get(x.avenue, 9), x.name)):
		row = {
			"course": req.name,
			"course_title": req.course_title,
			"avenue": req.avenue,
			"delivery_method": req.delivery_method or _("TBD"),
			"frequency_summary": req.frequency_summary,
			"verification_method": req.verification_method or _("TBD"),
			"duration_minutes": req.duration_minutes,
		}
		for role in roles:
			row["r_" + frappe.scrub(role)] = (
				REQUIRED if req.all_employees else codes.get((req.name, role), NOT_REQUIRED)
			)
		data.append(row)
	if filters.get("training_role"):
		key = "r_" + frappe.scrub(filters.training_role)
		data = [d for d in data if d.get(key) != NOT_REQUIRED]
	return columns, data + total_rows(data, roles)


def add_skill_courses(codes: dict, roles: list[str]) -> None:
	"""Courses a role needs because the role needs a skill (stricter code wins)."""
	defs = sk.definitions()
	rank = {REQUIRED: 2, CONDITIONAL: 1}
	for role in roles:
		for skill, code in sk.role_skills([role]).items():
			for course in ss.skill_courses(defs, skill):
				if rank.get(code, 0) > rank.get(codes.get((course, role)), 0):
					codes[(course, role)] = code


def total_rows(data: list[dict], roles: list[str]) -> list[dict]:
	"""Required hours, conditional hours and courses still missing a duration, per role."""
	if not data:
		return []
	rows = [
		{"course_title": _("Required training (hours)"), "is_total": 1},
		{"course_title": _("Conditional training (hours)"), "is_total": 1},
		{"course_title": _("Courses with no duration yet"), "is_total": 1},
	]
	for role in roles:
		key = "r_" + frappe.scrub(role)
		required = [d for d in data if d.get(key) == REQUIRED]
		conditional = [d for d in data if d.get(key) == CONDITIONAL]
		rows[0][key] = hours(required)
		rows[1][key] = hours(conditional)
		missing = sum(1 for d in required + conditional if not d.get("duration_minutes"))
		rows[2][key] = str(missing) if missing else NOT_REQUIRED
	rows[0]["duration_minutes"] = sum(d.get("duration_minutes") or 0 for d in data)
	return rows


def hours(rows: list[dict]) -> str:
	minutes = sum(d.get("duration_minutes") or 0 for d in rows)
	return f"{minutes / 60:.1f}" if rows else NOT_REQUIRED
