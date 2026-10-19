# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe

from hse.training_matrix import lms

MODULE = "Training Matrix"
# TRN-700 Rev 1 §3.2: maintains the matrix, schedules training, sends the monthly report.
TRAINING_COORDINATOR = "Training Coordinator"
# TRN-700 Rev 1 §4.8: given automatically to trainers with an active Qualified Trainer course.
QUALIFIED_TRAINER = "Qualified Trainer"


def make_roles():
	for role in (TRAINING_COORDINATOR, QUALIFIED_TRAINER):
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


def after_install():
	make_roles()
	lms.setup()


def after_migrate():
	make_roles()
	lms.setup()
