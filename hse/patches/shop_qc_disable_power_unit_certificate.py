import frappe


def execute():
	"""Power Units now use the combined System Construction Test Record.

	Frappe keeps a print format's Disabled flag on migrate, so the standard
	Power Unit QC Certificate is disabled here once."""
	if frappe.db.exists("Print Format", "Power Unit QC Certificate"):
		frappe.db.set_value("Print Format", "Power Unit QC Certificate", "disabled", 1, update_modified=False)
