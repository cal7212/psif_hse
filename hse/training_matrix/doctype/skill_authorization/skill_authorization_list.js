// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.listview_settings["Skill Authorization"] = {
	add_fields: ["docstatus", "expires_on"],
	get_indicator(doc) {
		if (doc.docstatus === 2) return [__("Revoked"), "gray", "docstatus,=,2"];
		if (doc.docstatus === 0) return [__("Draft"), "orange", "docstatus,=,0"];
		if (doc.expires_on && doc.expires_on < frappe.datetime.get_today())
			return [__("Expired"), "red", "docstatus,=,1"];
		return [__("Authorized"), "green", "docstatus,=,1"];
	},
};
