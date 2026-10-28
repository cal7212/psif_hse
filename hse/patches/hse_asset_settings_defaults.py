import frappe

SETTINGS = "HSE Asset Settings"


def execute():
	"""Save the field default (0.01) so the Single shows it before anyone opens it."""
	if frappe.db.get_single_value(SETTINGS, "placeholder_purchase_amount"):
		return
	default = frappe.get_meta(SETTINGS).get_field("placeholder_purchase_amount").default
	frappe.db.set_single_value(SETTINGS, "placeholder_purchase_amount", default)
