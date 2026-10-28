from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Housekeeping Inspection"


def get_custom_fields():
	# The NCR fields are part of the Nonconformance Report doctype.
	return {}


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
