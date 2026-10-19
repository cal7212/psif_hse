# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from hse.training_matrix.portal import my_training_context, own_employee

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/my-training"
		raise frappe.Redirect
	context.title = _("My Training")
	context.no_breadcrumbs = True
	context.employee = own_employee()
	if context.employee:
		context.update(my_training_context(context.employee))
	return context
