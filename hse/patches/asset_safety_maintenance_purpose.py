import frappe

SETTINGS = "HSE Asset Settings"
TEMPLATE = "Asset Inspection Template"
FORKLIFT = "Forklift - Daily Pre-Shift Inspection"


def execute():
	"""Safety versus maintenance split.

	- Save the Safety Asset Category default ("Safety Equipment") when it is blank and exists.
	- The forklift daily pre-shift check is an OSHA-required pre-use inspection, so its template
	  Purpose is Safety. Only set when the template exists and its Purpose is blank.
	"""
	frappe.reload_doc("asset_inspection", "doctype", "hse_asset_settings")
	frappe.reload_doc("asset_inspection", "doctype", "asset_inspection_template")
	if not frappe.db.get_single_value(SETTINGS, "safety_asset_category") and frappe.db.exists(
		"Asset Category", "Safety Equipment"
	):
		frappe.db.set_single_value(SETTINGS, "safety_asset_category", "Safety Equipment")
	if frappe.db.exists(TEMPLATE, FORKLIFT) and not frappe.db.get_value(
		TEMPLATE, FORKLIFT, "inspection_purpose"
	):
		frappe.db.set_value(TEMPLATE, FORKLIFT, "inspection_purpose", "Safety", update_modified=False)
