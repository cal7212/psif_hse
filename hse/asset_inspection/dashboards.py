from frappe import _

# Asset Maintenance is named after its Asset (autoname "field:asset_name"),
# so Asset Inspection.asset matches Asset Maintenance.name directly.


def _add_group(data, label, items):
	data.setdefault("transactions", [])
	for group in data["transactions"]:
		if group.get("label") == label:
			group["items"] = list(dict.fromkeys(group.get("items", []) + items))
			return data
	data["transactions"].append({"label": label, "items": items})
	return data


def asset_maintenance(data):
	data.setdefault("non_standard_fieldnames", {})
	data["non_standard_fieldnames"]["Asset Inspection"] = "asset"
	data["non_standard_fieldnames"]["Non Conformance"] = "asset"
	return _add_group(data, _("Inspections"), ["Asset Inspection", "Non Conformance"])


def asset(data):
	data.setdefault("non_standard_fieldnames", {})
	data["non_standard_fieldnames"]["Asset Inspection"] = "asset"
	data["non_standard_fieldnames"]["Non Conformance"] = "asset"
	data["non_standard_fieldnames"]["Vehicle"] = "asset"
	data["non_standard_fieldnames"]["Vehicle Log"] = "asset"
	_add_group(data, _("Inspections"), ["Asset Inspection", "Non Conformance"])
	return _add_group(data, _("Vehicle"), ["Vehicle", "Vehicle Log"])


def asset_maintenance_log(data):
	data.setdefault("non_standard_fieldnames", {})
	data["non_standard_fieldnames"]["Asset Inspection"] = "asset_maintenance_log"
	return _add_group(data, _("Inspections"), ["Asset Inspection"])
