# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe

MODULE = "Training Matrix"
# TRN-700 Rev 1 §3.2: maintains the matrix, schedules training, sends the monthly report.
TRAINING_COORDINATOR = "Training Coordinator"


def make_roles():
	if not frappe.db.exists("Role", TRAINING_COORDINATOR):
		frappe.get_doc({"doctype": "Role", "role_name": TRAINING_COORDINATOR, "desk_access": 1}).insert(
			ignore_permissions=True
		)


def after_install():
	make_roles()


def after_migrate():
	make_roles()
