# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""TRN-701 Part 2: Employee Training Status Matrix (TRN-700 Rev 1 Appendix A).

One row per employee, one column per course. Cells: C mm/dd/yy (completed and Qualified),
IP (in progress), D (due within 30 days), OD (overdue), ? (conditional, applicability not
confirmed), — (not required). % Complete = completed required courses ÷ total required courses.
"""

import frappe
from frappe import _

from hse.training_matrix import status as st

AVENUE_ORDER = {"HR Onboarding": 0, "Safety / EHS": 1, "QMS": 2, "Technical": 3}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	matrices = get_matrices(filters)
	if not matrices:
		return base_columns(), []
	items = get_items([m.name for m in matrices], filters)
	courses = get_courses(items)
	columns = base_columns() + [
		{"label": c.name, "fieldname": fieldname(c.name), "fieldtype": "Data", "width": 82} for c in courses
	]
	columns += [
		{"label": _("% Complete"), "fieldname": "percent_complete", "fieldtype": "Percent", "width": 95},
		{"label": _("Overdue"), "fieldname": "overdue_count", "fieldtype": "Int", "width": 75},
	]
	by_matrix: dict[str, list] = {}
	for it in items:
		by_matrix.setdefault(it.parent, []).append(it)
	data = []
	for m in matrices:
		row = {
			"employee": m.employee,
			"employee_name": m.employee_name,
			"department": m.department,
			"roles": m.roles,
			"date_of_joining": m.date_of_joining,
		}
		for it in by_matrix.get(m.name, []):
			row[fieldname(it.training_requirement)] = st.matrix_code(it.status, it.completed_on)
		rows = by_matrix.get(m.name, [])
		row["percent_complete"] = (
			st.percent_complete(rows)
			if filters.get("training_requirement") or filters.get("avenue")
			else m.percent_complete
		)
		row["overdue_count"] = sum(1 for it in rows if it.is_required and it.status == st.OVERDUE)
		data.append(row)
	return columns, data


def fieldname(course: str) -> str:
	return "c_" + frappe.scrub(course).replace("-", "_")


def base_columns():
	return [
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
		{"label": _("Training Role"), "fieldname": "roles", "fieldtype": "Data", "width": 130},
		{"label": _("Hire Date"), "fieldname": "date_of_joining", "fieldtype": "Date", "width": 95},
	]


def get_matrices(filters):
	conditions = {} if filters.get("include_inactive") else {"active": 1}
	for key in ("employee", "department", "company"):
		if filters.get(key):
			conditions[key] = filters.get(key)
	if filters.get("training_role"):
		conditions["name"] = [
			"in",
			frappe.get_all(
				"Employee Training Matrix Role",
				filters={"training_role": filters.training_role, "parenttype": "Employee Training Matrix"},
				pluck="parent",
			)
			or [""],
		]
	if filters.get("overdue_only"):
		conditions["overdue_count"] = [">", 0]
	matrices = frappe.get_list(
		"Employee Training Matrix",
		filters=conditions,
		fields=["name", "employee", "employee_name", "department", "date_of_joining", "percent_complete"],
		order_by="department asc, employee_name asc",
		limit_page_length=0,
	)
	roles = {}
	for r in frappe.get_all(
		"Employee Training Matrix Role",
		filters={
			"parent": ["in", [m.name for m in matrices] or [""]],
			"parenttype": "Employee Training Matrix",
		},
		fields=["parent", "training_role"],
	):
		roles.setdefault(r.parent, []).append(r.training_role)
	for m in matrices:
		m.roles = ", ".join(sorted(roles.get(m.name, [])))
	return matrices


def get_items(parents, filters):
	conditions = {"parent": ["in", parents], "parenttype": "Employee Training Matrix"}
	if filters.get("avenue"):
		conditions["avenue"] = filters.avenue
	if filters.get("training_requirement"):
		conditions["training_requirement"] = filters.training_requirement
	if filters.get("high_hazard_only"):
		conditions["high_hazard"] = 1
	return frappe.get_all(
		"Employee Training Matrix Item",
		filters=conditions,
		fields=[
			"parent",
			"training_requirement",
			"avenue",
			"status",
			"completed_on",
			"is_required",
			"qualification",
		],
	)


def get_courses(items):
	"""Courses required (or to be confirmed) for at least one listed employee, in Appendix A order."""
	shown = {it.training_requirement: it.avenue for it in items if it.status != st.NOT_APPLICABLE}
	courses = [frappe._dict(name=n, avenue=a) for n, a in shown.items()]
	return sorted(courses, key=lambda c: (AVENUE_ORDER.get(c.avenue, 9), c.name))
