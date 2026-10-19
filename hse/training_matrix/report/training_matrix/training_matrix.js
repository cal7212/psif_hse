// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.query_reports["Training Matrix"] = {
	filters: [
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
		},
		{
			fieldname: "training_role",
			label: __("Training Role"),
			fieldtype: "Link",
			options: "Training Role",
		},
		{
			fieldname: "avenue",
			label: __("Avenue"),
			fieldtype: "Select",
			options: "\nHR Onboarding\nSafety / EHS\nQMS\nTechnical",
		},
		{
			fieldname: "training_requirement",
			label: __("Course"),
			fieldtype: "Link",
			options: "Training Requirement",
		},
		{ fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee" },
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{
			fieldname: "high_hazard_only",
			label: __("High-Hazard Courses Only"),
			fieldtype: "Check",
		},
		{
			fieldname: "overdue_only",
			label: __("Employees With Overdue Training"),
			fieldtype: "Check",
		},
		{
			fieldname: "include_inactive",
			label: __("Include Inactive Employees"),
			fieldtype: "Check",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (!column.fieldname.startsWith("c_")) return formatted;
		const colors = {
			C: "var(--green-600)",
			IP: "var(--blue-600)",
			D: "var(--orange-600)",
			OD: "var(--red-600)",
			"?": "var(--purple-600)",
			"—": "var(--gray-400)",
		};
		const code = (value || "").split(" ")[0];
		const color = colors[code];
		if (!color) return formatted;
		const weight = code === "OD" ? 700 : 500;
		return `<span style="color: ${color}; font-weight: ${weight}">${formatted}</span>`;
	},
};
