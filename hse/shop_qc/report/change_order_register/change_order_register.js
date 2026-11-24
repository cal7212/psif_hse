// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.query_reports["Change Order Register"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date" },
		{ fieldname: "qc_unit", label: __("QC Unit"), fieldtype: "Link", options: "QC Unit" },
		{
			fieldname: "change_type",
			label: __("Change Type"),
			fieldtype: "Select",
			options: "\nDesign\nProduction",
		},
		{
			fieldname: "source",
			label: __("Source"),
			fieldtype: "Select",
			options: "\nCustomer\nEngineering & Design\nProduction",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nPending\nApproved\nRejected\nCancelled",
		},
		{ fieldname: "only_open", label: __("Only Open Change Orders"), fieldtype: "Check" },
	],
	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (column.fieldname === "open_reason" && value) {
			return `<span style="color: var(--orange-600); font-weight: 600">${formatted}</span>`;
		}
		return formatted;
	},
};
