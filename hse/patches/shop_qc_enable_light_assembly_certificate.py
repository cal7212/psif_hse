import frappe


def execute():
	"""Light Assembly units print the short QC certificate again (HPU keeps the combined record).

	Frappe keeps a print format's Disabled flag on migrate, so it is re-enabled here once."""
	if frappe.db.exists("Print Format", "Power Unit QC Certificate"):
		frappe.db.set_value("Print Format", "Power Unit QC Certificate", "disabled", 0, update_modified=False)
