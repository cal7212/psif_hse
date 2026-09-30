from frappe import _


def _add_group(data, label, items):
	data.setdefault("transactions", [])
	for group in data["transactions"]:
		if group.get("label") == label:
			group["items"] = list(dict.fromkeys(group.get("items", []) + items))
			return data
	data["transactions"].append({"label": label, "items": items})
	return data


def location(data):
	"""Adds a Housekeeping group to the Location form's Connections tab."""
	data.setdefault("fieldname", "location")
	data.setdefault("non_standard_fieldnames", {})
	data["non_standard_fieldnames"]["Housekeeping Area"] = "location"
	data["non_standard_fieldnames"]["Housekeeping Inspection"] = "location"
	return _add_group(data, _("Housekeeping"), ["Housekeeping Area", "Housekeeping Inspection"])
