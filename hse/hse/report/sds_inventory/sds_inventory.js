// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.query_reports["SDS Inventory"] = {
	filters: [
		{ fieldname: "location", label: __("Location"), fieldtype: "Link", options: "Location" },
		{ fieldname: "status", label: __("Status"), fieldtype: "Select", options: "\nActive\nSuperseded\nDiscontinued", default: "Active" },
		{ fieldname: "current_only", label: __("Currently In Use Only"), fieldtype: "Check", default: 1 },
		{ fieldname: "unassigned_only", label: __("No Location Assigned"), fieldtype: "Check" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "signal_word" && data && data.signal_word === "Danger") {
			value = `<span style="color: var(--red-600); font-weight: 600">${value}</span>`;
		}
		return value;
	},
};
