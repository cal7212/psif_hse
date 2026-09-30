from frappe import _


def get_data():
	return {
		"fieldname": "housekeeping_area",
		"transactions": [
			{"label": _("Inspections"), "items": ["Housekeeping Inspection", "Non Conformance"]},
		],
	}
