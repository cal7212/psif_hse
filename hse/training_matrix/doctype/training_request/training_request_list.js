// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.listview_settings["Training Request"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		const colors = {
			Pending: "orange",
			Approved: "blue",
			Rejected: "red",
			Completed: "green",
			Cancelled: "gray",
		};
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
