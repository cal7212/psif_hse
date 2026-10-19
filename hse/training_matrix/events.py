# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Employee hooks: keep each employee's TRN-701 matrix in step with HR."""

import frappe
from frappe import _

from hse.training_matrix.matrix import EMP_FIELDS, sync_matrix

# HR fields the matrix and its roles depend on.
WATCHED = tuple(f for f in EMP_FIELDS if f != "name")


def employee_on_update(doc, method=None):
	"""Create or update the matrix when an employee is added or a watched field changes.

	A failure is logged and reported but never blocks saving the Employee."""
	if not (doc.flags.in_insert or any(doc.has_value_changed(f) for f in WATCHED)):
		return
	frappe.db.savepoint("training_matrix_sync")
	try:
		sync_matrix(doc.name)
	except Exception:
		frappe.db.rollback(save_point="training_matrix_sync")
		frappe.log_error(title=f"Training Matrix sync failed: {doc.name}")
		frappe.msgprint(
			_("The training matrix for {0} could not be updated. See the Error Log.").format(doc.name),
			indicator="orange",
			alert=True,
		)


def employee_group_on_update(doc, method=None):
	"""Adding or removing someone from an Employee Group mapped to a Training Role updates their matrix."""
	before = doc.get_doc_before_save()
	now = {r.employee for r in doc.employee_list}
	was = {r.employee for r in before.employee_list} if before else set()
	_sync_group_members(doc.name, now ^ was if before else now)


def employee_group_on_trash(doc, method=None):
	_sync_group_members(doc.name, {r.employee for r in doc.employee_list}, deleted=True)


def _sync_group_members(group: str, employees: set[str], deleted: bool = False):
	"""Re-sync the affected members. Like employee_on_update, never blocks saving the group."""
	if not employees or not frappe.db.exists("DocType", "Employee Training Matrix"):
		return
	if not frappe.db.exists(
		"Training Role Employee Group", {"employee_group": group, "parenttype": "Training Role"}
	):
		return  # group not used for training
	if deleted:  # membership rows are still in the database during on_trash
		frappe.db.delete("Employee Group Table", {"parent": group, "parenttype": "Employee Group"})
	for employee in sorted(employees):
		if not frappe.db.exists("Employee", employee):
			continue
		frappe.db.savepoint("training_matrix_group_sync")
		try:
			sync_matrix(employee)
		except Exception:
			frappe.db.rollback(save_point="training_matrix_group_sync")
			frappe.log_error(title=f"Training Matrix sync failed: {employee}")
			frappe.msgprint(
				_("The training matrix for {0} could not be updated. See the Error Log.").format(employee),
				indicator="orange",
				alert=True,
			)
