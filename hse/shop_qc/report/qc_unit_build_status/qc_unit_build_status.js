// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const QC_STATUS_COLORS = {
	"Pending Build": "gray",
	"In Build": "blue",
	"QC Hold": "red",
	"Ready for Release": "orange",
	Released: "green",
	Shipped: "green",
	Cancelled: "gray",
};

frappe.query_reports["QC Unit Build Status"] = {
	filters: [
		{ fieldname: "shop", label: __("Shop"), fieldtype: "Link", options: "Build Shop" },
		{
			fieldname: "product_type",
			label: __("Product Type"),
			fieldtype: "Select",
			options: "\nPower Unit\nManifold\nValve Stand\nHose Assembly\nComponent\nOther",
		},
		{
			fieldname: "job_type",
			label: __("Job Type"),
			fieldtype: "Select",
			options: "\nNew Build\nRepair",
		},
		{
			fieldname: "status",
			label: __("QC Status"),
			fieldtype: "Select",
			options:
				"\nPending Build\nIn Build\nQC Hold\nReady for Release\nReleased\nShipped\nCancelled",
		},
		{
			fieldname: "include_completed",
			label: __("Include Released, Shipped and Cancelled"),
			fieldtype: "Check",
		},
		{
			fieldname: "missing_parts",
			label: __("Only Units With Missing Parts"),
			fieldtype: "Check",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		const formatted = default_formatter(value, row, column, data);
		if (column.fieldname === "status" && value) {
			const color = QC_STATUS_COLORS[value] || "gray";
			return `<span class="indicator-pill ${color}">${formatted}</span>`;
		}
		if (["open_ncs", "missing_parts"].includes(column.fieldname) && value > 0) {
			return `<span style="color: var(--red-600); font-weight: 600">${formatted}</span>`;
		}
		return formatted;
	},
};
