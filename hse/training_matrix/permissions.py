# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Employees see only their own training matrix; HR, the Training Coordinator and Quality see all."""

import frappe

FULL_ACCESS = ("System Manager", "HR Manager", "HR User", "Training Coordinator", "Quality Manager")


def _full_access(user: str) -> bool:
	return user == "Administrator" or bool(set(frappe.get_roles(user)) & set(FULL_ACCESS))


def _own_employees(user: str) -> list[str]:
	return frappe.get_all("Employee", filters={"user_id": user}, pluck="name")


def _visible_employees_sql(user: str) -> str:
	"""The user's own employee record and their direct reports (managers review their team)."""
	own = "(select `name` from `tabEmployee` where `user_id` = {0})".format(frappe.db.escape(user))
	return f"(select `name` from `tabEmployee` where `name` in {own} or `reports_to` in {own})"


def _visible_employees(user: str) -> set[str]:
	own = _own_employees(user)
	if not own:
		return set()
	return set(own) | set(frappe.get_all("Employee", filters={"reports_to": ["in", own]}, pluck="name"))


def matrix_query_conditions(user: str | None = None, **kwargs) -> str:
	user = user or frappe.session.user
	if _full_access(user):
		return ""
	return f"`tabEmployee Training Matrix`.`employee` in {_visible_employees_sql(user)}"


def matrix_has_permission(doc, ptype=None, user=None, **kwargs) -> bool | None:
	user = user or frappe.session.user
	if _full_access(user):
		return None  # role permissions decide
	return doc.employee in _visible_employees(user) and ptype in ("read", "print", "report", "export")


# ---------------------------------------------------------------- Training Record / Competency Evaluation
# Trainers (Qualified Trainer role) and employees see the records they trained, attended or were
# evaluated on; the roles in FULL_ACCESS see everything.
def _employees_sql(user: str) -> str:
	return "(select `name` from `tabEmployee` where `user_id` = {0})".format(frappe.db.escape(user))


def record_query_conditions(user: str | None = None, **kwargs) -> str:
	user = user or frappe.session.user
	if _full_access(user):
		return ""
	emp = _employees_sql(user)
	return (
		f"(`tabTraining Record`.`trainer` in {emp} or `tabTraining Record`.`owner` = {frappe.db.escape(user)}"
		f" or `tabTraining Record`.`name` in (select `parent` from `tabTraining Record Attendee`"
		f" where `parenttype` = 'Training Record' and `employee` in {emp}))"
	)


def record_has_permission(doc, ptype=None, user=None, **kwargs) -> bool | None:
	user = user or frappe.session.user
	if _full_access(user) or doc.is_new():
		return None
	own = set(_own_employees(user))
	if doc.owner == user or doc.trainer in own:
		return None
	return ptype in ("read", "print") and any(a.employee in own for a in doc.attendees)


def evaluation_query_conditions(user: str | None = None, **kwargs) -> str:
	user = user or frappe.session.user
	if _full_access(user):
		return ""
	emp = _employees_sql(user)
	return (
		f"(`tabCompetency Evaluation`.`employee` in {emp} or `tabCompetency Evaluation`.`evaluator` in {emp}"
		f" or `tabCompetency Evaluation`.`owner` = {frappe.db.escape(user)})"
	)


def evaluation_has_permission(doc, ptype=None, user=None, **kwargs) -> bool | None:
	user = user or frappe.session.user
	if _full_access(user) or doc.is_new():
		return None
	own = set(_own_employees(user))
	if doc.owner == user or doc.evaluator in own:
		return None
	return ptype in ("read", "print") and doc.employee in own


# ---------------------------------------------------------------- Skill Authorization
def authorization_query_conditions(user: str | None = None, **kwargs) -> str:
	user = user or frappe.session.user
	if _full_access(user):
		return ""
	return (
		f"(`tabSkill Authorization`.`employee` in {_visible_employees_sql(user)}"
		f" or `tabSkill Authorization`.`authorized_by` = {frappe.db.escape(user)})"
	)


def authorization_has_permission(doc, ptype=None, user=None, **kwargs) -> bool | None:
	user = user or frappe.session.user
	if _full_access(user) or doc.is_new() or doc.authorized_by == user:
		return None  # creating is checked by the controller (manager of the employee)
	if doc.employee in _own_employees(user):
		return ptype in ("read", "print")
	return doc.employee in _visible_employees(user) or None
