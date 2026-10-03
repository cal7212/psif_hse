from frappe import _


def get_data():
	return {
		"fieldname": "qc_unit",
		"transactions": [
			{"label": _("Quality"), "items": ["QC Inspection", "Non Conformance"]},
		],
	}
