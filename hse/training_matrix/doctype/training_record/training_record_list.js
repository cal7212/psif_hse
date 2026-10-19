// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.listview_settings["Training Record"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		const colors = {
			Draft: "orange",
			"Awaiting Acknowledgment": "purple",
			Complete: "green",
			Cancelled: "gray",
		};
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
