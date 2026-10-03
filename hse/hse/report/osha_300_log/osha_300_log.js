// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.query_reports["OSHA 300 Log"] = {
	filters: [
		{
			fieldname: "year",
			label: __("Year"),
			fieldtype: "Int",
			default: new Date().getFullYear(),
			reqd: 1,
		},
		{
			fieldname: "include_drafts",
			label: __("Include Draft Reports"),
			fieldtype: "Check",
		},
	],
	onload(report) {
		report.page.add_inner_button(__("OSHA 300A Summary"), () => {
			const year = report.get_filter_value("year");
			frappe.db.get_value("OSHA 300A Summary", { year }, "name").then(({ message }) => {
				if (message && message.name)
					frappe.set_route("Form", "OSHA 300A Summary", message.name);
				else frappe.new_doc("OSHA 300A Summary", { year });
			});
		});
	},
};
