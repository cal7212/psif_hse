from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Asset Inspection"


def get_custom_fields():
	return {
		"Asset": [
			{
				"fieldname": "safety_status",
				"label": "Safety Status",
				"fieldtype": "Select",
				"options": "In Service\nOut of Service",
				"default": "In Service",
				"insert_after": "status",
				"read_only": 1,
				"allow_on_submit": 1,
				"in_list_view": 1,
				"in_standard_filter": 1,
				"no_copy": 1,
				"description": "Set automatically by Asset Inspections and Non Conformance.",
			},
		],
		"Asset Maintenance Task": [
			{
				"fieldname": "inspection_template",
				"label": "Inspection Template",
				"fieldtype": "Link",
				"options": "Asset Inspection Template",
				"insert_after": "maintenance_type",
			},
		],
		"Asset Maintenance Log": [
			{
				"fieldname": "asset_inspection",
				"label": "Asset Inspection",
				"fieldtype": "Link",
				"options": "Asset Inspection",
				"insert_after": "maintenance_status",
				"read_only": 1,
				"allow_on_submit": 1,
				"no_copy": 1,
			},
		],
		"Non Conformance": [
			{
				"fieldname": "asset_inspection_section",
				"label": "Inspection Follow-up",
				"fieldtype": "Section Break",
				"insert_after": "status",
				"collapsible": 0,
			},
			{
				"fieldname": "asset",
				"label": "Asset",
				"fieldtype": "Link",
				"options": "Asset",
				"insert_after": "asset_inspection_section",
				"in_standard_filter": 1,
			},
			{
				"fieldname": "asset_inspection",
				"label": "Asset Inspection",
				"fieldtype": "Link",
				"options": "Asset Inspection",
				"insert_after": "asset",
				"read_only": 1,
			},
			{
				"fieldname": "severity",
				"label": "Severity",
				"fieldtype": "Select",
				"options": "\nLow\nMedium\nHigh\nCritical",
				"insert_after": "asset_inspection",
				"in_list_view": 1,
				"in_standard_filter": 1,
			},
			{
				"fieldname": "si_column_break",
				"fieldtype": "Column Break",
				"insert_after": "severity",
			},
			{
				"fieldname": "interim_control",
				"label": "Interim Control",
				"fieldtype": "Small Text",
				"insert_after": "si_column_break",
				"description": "e.g. tagged out, barricaded, removed from service",
			},
			{
				"fieldname": "verified_by",
				"label": "Verified By",
				"fieldtype": "Link",
				"options": "Employee",
				"insert_after": "interim_control",
			},
			{
				"fieldname": "verification_date",
				"label": "Verification Date",
				"fieldtype": "Date",
				"insert_after": "verified_by",
			},
			{
				"fieldname": "reinspection",
				"label": "Re-inspection",
				"fieldtype": "Link",
				"options": "Asset Inspection",
				"insert_after": "verification_date",
				"read_only": 1,
			},
		],
	}


def make_custom_fields():
	fields = get_custom_fields()
	for rows in fields.values():
		for row in rows:
			row["module"] = MODULE
	create_custom_fields(fields, update=True)


def after_install():
	make_custom_fields()


def after_migrate():
	make_custom_fields()
