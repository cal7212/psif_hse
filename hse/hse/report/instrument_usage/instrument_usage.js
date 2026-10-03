// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.query_reports["Instrument Usage"] = {
	filters: [
		{
			fieldname: "instrument",
			label: __("Instrument"),
			fieldtype: "Link",
			options: "Measuring Instrument",
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			description: __("e.g. the last good calibration date"),
		},
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date" },
		{
			fieldname: "inspection_type",
			label: __("Inspection Type"),
			fieldtype: "Select",
			options: ["", "QC Inspection", "Asset Inspection"],
		},
	],
};
