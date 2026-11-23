// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.listview_settings["Confined Space Permit"] = {
	add_fields: ["status", "docstatus", "permit_end"],
	get_indicator: (doc) => window.hse.permits.indicator(doc, "Issued", "permit_end"),
};
