import frappe

OUT_OF_SERVICE = "Out of Service"
IN_SERVICE = "In Service"


def update_asset_safety_status(asset: str) -> str:
	"""Asset is Out of Service while any Open Non Conformance with Critical
	severity exists against it; otherwise In Service."""
	if not asset or not frappe.db.exists("Asset", asset):
		return None

	has_open_critical = frappe.db.exists(
		"Non Conformance",
		{"asset": asset, "status": "Open", "severity": "Critical"},
	)
	new_status = OUT_OF_SERVICE if has_open_critical else IN_SERVICE

	if frappe.db.get_value("Asset", asset, "safety_status") != new_status:
		# Asset is usually submitted; db.set_value bypasses submit locks.
		frappe.db.set_value("Asset", asset, "safety_status", new_status)
		frappe.get_doc("Asset", asset).add_comment(
			"Info", f"Safety Status set to {new_status}"
		)
	return new_status


def assert_asset_in_service(asset: str):
	"""Call from any DocType that assigns or uses equipment (checkout,
	pre-shift check, work order) to block Out of Service assets."""
	if frappe.db.get_value("Asset", asset, "safety_status") == OUT_OF_SERVICE:
		frappe.throw(
			f"{asset} is Out of Service pending corrective action.",
			title="Asset Out of Service",
		)
