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
