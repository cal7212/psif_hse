// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.listview_settings["Risk Assessment"] = {
	add_fields: ["status", "docstatus", "next_review_date", "highest_residual_rating"],
	get_indicator(doc) {
		if (doc.docstatus === 0) return [__("Draft"), "gray", "docstatus,=,0"];
		if (doc.status === "Cancelled") return [__("Cancelled"), "red", "status,=,Cancelled"];
		if (doc.status === "Superseded")
			return [__("Superseded"), "darkgrey", "status,=,Superseded"];
		if (doc.next_review_date && doc.next_review_date <= frappe.datetime.get_today()) {
			return [
				__("Review Due"),
				"orange",
				`status,=,Active|next_review_date,<=,${frappe.datetime.get_today()}`,
			];
		}
		return [__("Active"), "green", "status,=,Active"];
	},
};
