from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Housekeeping Inspection"


def get_custom_fields():
	# Reuses severity / interim_control / verified_by / verification_date /
	# corrective_action on Non Conformance (created by the Asset Inspection module).
	return {
		"Non Conformance": [
			{
				"fieldname": "housekeeping_section",
				"label": "Housekeeping Inspection",
				"fieldtype": "Section Break",
				"insert_after": "reinspection",
				"depends_on": "eval:doc.housekeeping_area || doc.housekeeping_inspection",
			},
			{
				"fieldname": "housekeeping_area",
				"label": "Housekeeping Area",
				"fieldtype": "Link",
				"options": "Housekeeping Area",
				"insert_after": "housekeeping_section",
				"in_standard_filter": 1,
			},
			{
				"fieldname": "housekeeping_inspection",
				"label": "Housekeeping Inspection",
				"fieldtype": "Link",
				"options": "Housekeeping Inspection",
				"insert_after": "housekeeping_area",
				"read_only": 1,
			},
			{
				"fieldname": "hk_column_break",
				"fieldtype": "Column Break",
				"insert_after": "housekeeping_inspection",
			},
			{
				"fieldname": "housekeeping_reinspection",
				"label": "Housekeeping Re-inspection",
				"fieldtype": "Link",
				"options": "Housekeeping Inspection",
				"insert_after": "hk_column_break",
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
