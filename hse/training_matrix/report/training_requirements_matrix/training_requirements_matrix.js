// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.query_reports["Training Requirements Matrix"] = {
	filters: [
		{
			fieldname: "avenue",
			label: __("Avenue"),
			fieldtype: "Select",
			options: "\nHR Onboarding\nSafety / EHS\nQMS\nTechnical",
		},
		{
			fieldname: "training_role",
			label: __("Training Role"),
			fieldtype: "Link",
			options: "Training Role",
		},
		{
			fieldname: "include_disabled",
			label: __("Include Disabled Courses"),
			fieldtype: "Check",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (column.fieldname.startsWith("r_") && value === "R") return `<b>${formatted}</b>`;
		if (column.fieldname.startsWith("r_") && value === "—")
			return `<span style="color: var(--gray-400)">${formatted}</span>`;
		if (value === "TBD") return `<span style="color: var(--orange-600)">${formatted}</span>`;
		return formatted;
	},
};
