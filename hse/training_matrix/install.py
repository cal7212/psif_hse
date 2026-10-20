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


def default_settings():
	"""Escalations and the company-wide report go to the HR Manager until Settings say otherwise."""
	if not frappe.db.exists("DocType", "Training Matrix Settings"):
		return
	settings = frappe.get_single("Training Matrix Settings")
	if settings.escalation_days:
		return  # already set up
	settings.update(
		{
			"escalation_days": 14,
			"monthly_email": 1,
			"absence_days": 90,
			"absence_due_days": 0,
			"certificate_business_days": 10,
		}
	)
	if not settings.escalation_roles and not settings.escalation_users:
		settings.append("escalation_roles", {"role": "HR Manager"})
	settings.flags.ignore_permissions = True
	settings.save()


def after_install():
	make_roles()
	lms.setup()
	default_settings()


def after_migrate():
	make_roles()
	default_settings()
	lms.setup()
