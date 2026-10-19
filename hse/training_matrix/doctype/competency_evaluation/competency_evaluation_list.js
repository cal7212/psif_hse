// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.listview_settings["Competency Evaluation"] = {
	add_fields: ["result", "docstatus"],
	get_indicator(doc) {
		if (doc.docstatus === 2) return [__("Cancelled"), "gray", "docstatus,=,2"];
		if (doc.docstatus === 0) return [__("Draft"), "orange", "docstatus,=,0"];
		if (doc.result === "Pass") return [__("Qualified"), "green", "result,=,Pass"];
		return [__("Not Qualified"), "red", "result,=,Fail"];
	},
};
