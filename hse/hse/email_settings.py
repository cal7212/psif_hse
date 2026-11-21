# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""PSIF IMS Email Settings: one switch per automatic email.

Switching an email off skips only the email; the record, status change or ToDo that goes with it
still happens. The HSE Snapshot emails keep their own switches in HSE Snapshot Settings.
"""

import frappe
from frappe.utils import cint

EMAIL_SETTINGS = "PSIF IMS Email Settings"
SWITCHES = (
	"escalation_email",
	"acknowledgment_email",
	"retraining_email",
	"monthly_email",
	"request_decision_email",
	"certificate_reminder_email",
	"assignment_emails",
)
# monthly_email used to live on Training Matrix Settings; its saved value carries over.
CARRIED_OVER = {"monthly_email": "Training Matrix Settings"}


def email_enabled(switch: str) -> bool:
	return bool(frappe.get_cached_doc(EMAIL_SETTINGS).get(switch))


def ensure_defaults() -> None:
	"""after_install / after_migrate: store every switch the site has not saved yet, ticked, so each
	email keeps going out as before until someone unticks it."""
	if not frappe.db.exists("DocType", EMAIL_SETTINGS):
		return
	saved = frappe.db.get_singles_dict(EMAIL_SETTINGS)
	missing = [s for s in SWITCHES if s not in saved]
	if not missing:
		return
	for switch in missing:
		frappe.db.set_single_value(EMAIL_SETTINGS, switch, old_value(switch))
	frappe.clear_document_cache(EMAIL_SETTINGS, EMAIL_SETTINGS)


def old_value(switch: str) -> int:
	doctype = CARRIED_OVER.get(switch)
	if not doctype:
		return 1
	singles = frappe.qb.DocType("Singles")
	row = (
		frappe.qb.from_(singles)
		.select(singles.value)
		.where((singles.doctype == doctype) & (singles.field == switch))
		.run()
	)
	return cint(row[0][0]) if row else 1
