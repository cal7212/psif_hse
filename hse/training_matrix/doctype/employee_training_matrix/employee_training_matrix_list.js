// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.listview_settings["Employee Training Matrix"] = {
	add_fields: ["active", "overdue_count", "due_count", "confirm_count", "percent_complete"],
	get_indicator(doc) {
		if (!doc.active) return [__("Inactive"), "gray", "active,=,0"];
		if (doc.overdue_count) return [__("Overdue"), "red", "overdue_count,>,0"];
		if (doc.due_count) return [__("Due"), "orange", "due_count,>,0"];
		if (doc.confirm_count) return [__("Confirm Conditional"), "purple", "confirm_count,>,0"];
		return [__("Current"), "green", "overdue_count,=,0"];
	},
};
