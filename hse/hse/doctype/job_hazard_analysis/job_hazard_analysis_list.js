// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.listview_settings["Job Hazard Analysis"] = {
	add_fields: ["status", "docstatus", "next_review_date"],
	get_indicator(doc) {
		if (doc.docstatus === 0) return [__("Draft"), "gray", "docstatus,=,0"];
		if (doc.status === "Cancelled") return [__("Cancelled"), "red", "status,=,Cancelled"];
		if (doc.status === "Superseded")
			return [__("Superseded"), "darkgrey", "status,=,Superseded"];
		const today = frappe.datetime.get_today();
		if (doc.next_review_date && doc.next_review_date <= today) {
			return [__("Review Due"), "orange", `status,=,Active|next_review_date,<=,${today}`];
		}
		return [__("Active"), "green", "status,=,Active"];
	},
};
