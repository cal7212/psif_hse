// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.query_reports["Skill Matrix"] = {
	filters: [
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
		},
		{ fieldname: "skill", label: __("Skill"), fieldtype: "Link", options: "Skill" },
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nNot Started\nIn Training\nReady for Authorization\nAuthorized\nLapsed",
		},
		{
			fieldname: "include_inactive",
			label: __("Include Inactive Employees"),
			fieldtype: "Check",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (!column.fieldname.startsWith("s_") || !value) return formatted;
		const colors = { A: "green", R: "purple", T: "blue", L: "red" };
		const color = colors[value.split(" ")[0]];
		return color
			? `<span style="color: var(--${color}-600); font-weight: 600">${formatted}</span>`
			: formatted;
	},
};
