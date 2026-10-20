# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Record-level access for the Training Matrix module.

Frappe only uses has_permission hooks to deny access: True means "no objection, role permissions
decide", and anything falsy, None included, is a denial. Every hook here returns a bool.

Who sees every record is set in Role Permission Manager: any role with read permission on the
DocType sees all of them. The roles below are scoped instead: they only see the user's own
records and their direct reports' (and, for trainers, the records they trained or evaluated).
"""

import frappe
import frappe.permissions

# Roles that never give company-wide access by themselves: every employee has the self-service
# roles, and Qualified Trainer is granted automatically to anyone on the trainer register.
SCOPED_ROLES = {
	"Employee",
	"Employee Self Service",
	"All",
	"Guest",
	"Desk User",
	"LMS Student",
	"Qualified Trainer",
}


def _full_access(user: str, doctype: str) -> bool:
	"""Company-wide access comes from Role Permission Manager: any role with read permission on the
	DocType, other than the scoped roles above, sees every record."""
	if user == "Administrator":
		return True
	if not any(r not in SCOPED_ROLES for r in frappe.get_roles(user)):
		return False
	# DocPerm and Custom DocPerm (Role Permission Manager), level 0, for the non-scoped roles only.
	# get_valid_perms(doctype, user) works on every v16 release (the roles= argument is newer).
	return any(
		p.get("read") and not p.get("permlevel") and p.get("role") not in SCOPED_ROLES
		for p in frappe.permissions.get_valid_perms(doctype, user)
	)


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
	if _full_access(user, "Employee Training Matrix"):
		return ""
	return f"`tabEmployee Training Matrix`.`employee` in {_visible_employees_sql(user)}"


def matrix_has_permission(doc, ptype=None, user=None, **kwargs) -> bool:
	user = user or frappe.session.user
	if _full_access(user, "Employee Training Matrix"):
		return True  # no objection: role permissions decide
	return doc.employee in _visible_employees(user) and ptype in ("read", "print", "report", "export")


# ---------------------------------------------------------------- Training Record / Competency Evaluation
# Trainers (Qualified Trainer role) and employees see the records they trained, attended or were
# evaluated on; roles with read permission on the DocType see everything.
def _employees_sql(user: str) -> str:
	return "(select `name` from `tabEmployee` where `user_id` = {0})".format(frappe.db.escape(user))


def record_query_conditions(user: str | None = None, **kwargs) -> str:
	user = user or frappe.session.user
	if _full_access(user, "Training Record"):
		return ""
	emp = _employees_sql(user)
	return (
		f"(`tabTraining Record`.`trainer` in {emp} or `tabTraining Record`.`owner` = {frappe.db.escape(user)}"
		f" or `tabTraining Record`.`name` in (select `parent` from `tabTraining Record Attendee`"
		f" where `parenttype` = 'Training Record' and `employee` in {emp}))"
	)


def record_has_permission(doc, ptype=None, user=None, **kwargs) -> bool:
	user = user or frappe.session.user
	if _full_access(user, "Training Record") or doc.is_new():
		return True
	own = set(_own_employees(user))
	if doc.owner == user or doc.trainer in own:
		return True
	return ptype in ("read", "print") and any(a.employee in own for a in doc.attendees)


def evaluation_query_conditions(user: str | None = None, **kwargs) -> str:
	user = user or frappe.session.user
	if _full_access(user, "Competency Evaluation"):
		return ""
	emp = _employees_sql(user)
	return (
		f"(`tabCompetency Evaluation`.`employee` in {emp} or `tabCompetency Evaluation`.`evaluator` in {emp}"
		f" or `tabCompetency Evaluation`.`owner` = {frappe.db.escape(user)})"
	)


def evaluation_has_permission(doc, ptype=None, user=None, **kwargs) -> bool:
	user = user or frappe.session.user
	if _full_access(user, "Competency Evaluation") or doc.is_new():
		return True
	own = set(_own_employees(user))
	if doc.owner == user or doc.evaluator in own:
		return True
	return ptype in ("read", "print") and doc.employee in own


# ---------------------------------------------------------------- Skill Authorization
def authorization_query_conditions(user: str | None = None, **kwargs) -> str:
	user = user or frappe.session.user
	if _full_access(user, "Skill Authorization"):
		return ""
	return (
		f"(`tabSkill Authorization`.`employee` in {_visible_employees_sql(user)}"
		f" or `tabSkill Authorization`.`authorized_by` = {frappe.db.escape(user)})"
	)


def authorization_has_permission(doc, ptype=None, user=None, **kwargs) -> bool:
	user = user or frappe.session.user
	if _full_access(user, "Skill Authorization") or doc.is_new() or doc.authorized_by == user:
		return True  # creating is checked by the controller (manager of the employee)
	if doc.employee in _own_employees(user):
		return ptype in ("read", "print")
	return doc.employee in _visible_employees(user)


# ---------------------------------------------------------------- Retraining Assignment / Training Request
# Managers see the assignments and requests of their team; employees see their own.
def assignment_query_conditions(user: str | None = None, **kwargs) -> str:
	user = user or frappe.session.user
	if _full_access(user, "Retraining Assignment"):
		return ""
	return (
		f"(`tabRetraining Assignment`.`owner` = {frappe.db.escape(user)}"
		" or `tabRetraining Assignment`.`name` in (select `parent` from `tabRetraining Assignment Employee`"
		f" where `parenttype` = 'Retraining Assignment' and `employee` in {_visible_employees_sql(user)}))"
	)


def assignment_has_permission(doc, ptype=None, user=None, **kwargs) -> bool:
	user = user or frappe.session.user
	if _full_access(user, "Retraining Assignment") or doc.is_new() or doc.owner == user:
		return True  # creating and submitting are checked by the controller (the employees' manager)
	visible = _visible_employees(user)
	if not any(r.employee in visible for r in doc.employees):
		return False
	own = set(_own_employees(user))
	only_self = all(r.employee in own for r in doc.employees)
	return ptype in ("read", "print") if only_self else True


def request_query_conditions(user: str | None = None, **kwargs) -> str:
	user = user or frappe.session.user
	if _full_access(user, "Training Request"):
		return ""
	return f"`tabTraining Request`.`employee` in {_visible_employees_sql(user)}"


def request_has_permission(doc, ptype=None, user=None, **kwargs) -> bool:
	user = user or frappe.session.user
	if _full_access(user, "Training Request") or doc.is_new():
		return True
	if doc.employee in _own_employees(user):
		return ptype in ("read", "print", "create")
	return doc.employee in _visible_employees(user) and ptype in ("read", "print")
