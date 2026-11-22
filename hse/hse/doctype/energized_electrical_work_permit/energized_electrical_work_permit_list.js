// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.listview_settings["Energized Electrical Work Permit"] = {
	add_fields: ["status", "docstatus", "work_end"],
	get_indicator: (doc) => window.hse.permits.indicator(doc, "Approved", "work_end"),
};
