from frappe import _


def get_data():
	return {
		"fieldname": "hpu_unit",
		"transactions": [
			{"label": _("Quality"), "items": ["HPU Build Inspection", "Non Conformance"]},
		],
	}
