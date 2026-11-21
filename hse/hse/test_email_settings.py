# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hse.hse.email_settings import EMAIL_SETTINGS, SWITCHES, email_enabled, ensure_defaults

OLD = "Training Matrix Settings"


def set_raw(doctype, field, value=None):
	"""Write or remove one stored Single value directly, as an older site would have it."""
	singles = frappe.qb.DocType("Singles")
	frappe.qb.from_(singles).delete().where((singles.doctype == doctype) & (singles.field == field)).run()
	if value is not None:
		frappe.qb.into(singles).columns("doctype", "field", "value").insert(doctype, field, value).run()
	frappe.clear_document_cache(doctype, doctype)


class IntegrationTestEmailSettings(IntegrationTestCase):
	def test_new_switches_start_on_and_monthly_carries_over(self):
		for switch in SWITCHES:
			set_raw(EMAIL_SETTINGS, switch)
		set_raw(OLD, "monthly_email", "0")  # the site had unticked the old monthly switch
		try:
			ensure_defaults()
			self.assertFalse(email_enabled("monthly_email"))
			for switch in SWITCHES:
				if switch != "monthly_email":
					self.assertTrue(email_enabled(switch), switch)
			# a saved choice is left alone on the next migrate
			frappe.db.set_single_value(EMAIL_SETTINGS, "retraining_email", 0)
			frappe.clear_document_cache(EMAIL_SETTINGS, EMAIL_SETTINGS)
			ensure_defaults()
			self.assertFalse(email_enabled("retraining_email"))
		finally:
			set_raw(OLD, "monthly_email")
			for switch in SWITCHES:
				frappe.db.set_single_value(EMAIL_SETTINGS, switch, 1)
			frappe.clear_document_cache(EMAIL_SETTINGS, EMAIL_SETTINGS)
