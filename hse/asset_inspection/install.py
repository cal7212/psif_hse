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
				"description": "Set automatically by Asset Inspections and Nonconformance Report.",
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
		# Vehicles: tie HR Vehicle / Vehicle Log (odometer, fuel) to the Asset
		"Vehicle": [
			{
				"fieldname": "asset",
				"label": "Asset",
				"fieldtype": "Link",
				"options": "Asset",
				"insert_after": "model",
				"unique": 1,
				"in_list_view": 1,
				"in_standard_filter": 1,
				"description": "Fixed asset used for pre-trip inspections. Fuel and mileage logs show on the Asset.",
			},
		],
		"Vehicle Log": [
			{
				"fieldname": "asset",
				"label": "Asset",
				"fieldtype": "Link",
				"options": "Asset",
				"insert_after": "make",
				"fetch_from": "license_plate.asset",
				"read_only": 1,
				"in_standard_filter": 1,
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
