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


def matrix_has_permission(doc, ptype=None, user=None, **kwargs) -> bool:
	"""Frappe only uses this hook to deny: True means "no objection, role permissions decide";
	anything falsy (including None) is a denial."""
	user = user or frappe.session.user
	if _full_access(user):
		return True
	return doc.employee in _own_employees(user)


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
