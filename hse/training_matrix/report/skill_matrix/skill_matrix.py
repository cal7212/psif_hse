# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Skill Matrix: one row per employee, one column per skill.

A = Authorized, R = Ready for Authorization, T = In Training, L = Lapsed, blank = Not Started.
"""

import frappe
from frappe import _

from hse.training_matrix import skill_status as ss

CODES = {ss.AUTHORIZED: "A", ss.READY: "R", ss.IN_TRAINING: "T", ss.LAPSED: "L", ss.NOT_STARTED: ""}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = {} if filters.get("include_inactive") else {"active": 1}
	if filters.get("department"):
		conditions["department"] = filters.department
	matrices = frappe.get_list(
		"Employee Training Matrix",
		filters=conditions,
		fields=["name", "employee", "employee_name", "department", "designation"],
		order_by="department asc, employee_name asc",
		limit_page_length=0,
	)
	row_filters = {
		"parenttype": "Employee Training Matrix",
		"parent": ["in", [m.name for m in matrices] or [""]],
	}
	if filters.get("skill"):
		row_filters["skill"] = filters.skill
	if filters.get("status"):
		row_filters["status"] = filters.status
	rows = frappe.get_all(
		"Employee Training Matrix Skill",
		filters=row_filters,
		fields=["parent", "skill", "status", "progress", "authorized_on"],
	)
	skills = sorted({r.skill for r in rows})
	by_matrix: dict[str, dict] = {}
	for r in rows:
		by_matrix.setdefault(r.parent, {})[r.skill] = r
	columns = [
		{
			"label": _("Employee"),
			"fieldname": "employee",
			"fieldtype": "Link",
			"options": "Employee",
			"width": 110,
		},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 170},
		{
			"label": _("Department"),
			"fieldname": "department",
			"fieldtype": "Link",
			"options": "Department",
			"width": 130,
		},
		{
			"label": _("Designation"),
			"fieldname": "designation",
			"fieldtype": "Link",
			"options": "Designation",
			"width": 130,
		},
	] + [{"label": s, "fieldname": "s_" + frappe.scrub(s), "fieldtype": "Data", "width": 120} for s in skills]
	data = []
	for m in matrices:
		held = by_matrix.get(m.name)
		if not held and (filters.get("skill") or filters.get("status")):
			continue
		row = {k: m[k] for k in ("employee", "employee_name", "department", "designation")}
		for skill, r in (held or {}).items():
			code = CODES.get(r.status, "")
			row["s_" + frappe.scrub(skill)] = (
				f"{code} ({r.progress})" if code in ("T", "") and r.progress else code
			)
		data.append(row)
	return columns, data
