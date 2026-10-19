# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Employees see only their own training matrix; HR, the Training Coordinator and Quality see all."""

import frappe

FULL_ACCESS = ("System Manager", "HR Manager", "HR User", "Training Coordinator", "Quality Manager")


def _full_access(user: str) -> bool:
	return user == "Administrator" or bool(set(frappe.get_roles(user)) & set(FULL_ACCESS))


def _own_employees(user: str) -> list[str]:
	return frappe.get_all("Employee", filters={"user_id": user}, pluck="name")


def matrix_query_conditions(user: str | None = None, **kwargs) -> str:
	user = user or frappe.session.user
	if _full_access(user):
		return ""
	return "`tabEmployee Training Matrix`.`employee` in (select `name` from `tabEmployee` where `user_id` = {0})".format(
		frappe.db.escape(user)
	)


def matrix_has_permission(doc, ptype=None, user=None, **kwargs) -> bool | None:
	user = user or frappe.session.user
	if _full_access(user):
		return None  # role permissions decide
	return doc.employee in _own_employees(user)
