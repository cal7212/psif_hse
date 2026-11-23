// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const RISK_REGISTER_COLORS = {
	Low: ["#d9f2d9", "#1e6b1e"],
	Medium: ["#fff3c4", "#7a5b00"],
	High: ["#ffd8b0", "#8a3c00"],
	Critical: ["#f8c4c4", "#8b0000"],
};

frappe.query_reports["Risk Register"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "location", label: __("Location"), fieldtype: "Link", options: "Location" },
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
		},
		{
			fieldname: "assessment_type",
			label: __("Assessment Type"),
			fieldtype: "Select",
			options:
				"\nTask / Job Hazard Analysis\nArea / Workplace\nEquipment / Machine\nChemical / Substance\nProcess Change\nOther",
		},
		{
			fieldname: "hazard_category",
			label: __("Hazard Category"),
			fieldtype: "Select",
			options:
				"\nMechanical / Moving Parts\nElectrical\nHydraulic / Stored Pressure\nChemical\nWelding / Hot Work\nFire / Explosion\nLifting / Rigging\nManual Handling / Ergonomic\nSlips / Trips / Falls\nWorking at Height\nForklift / Vehicle\nNoise\nThermal / Burns\nConfined Space\nBiological\nEnvironmental / Spill\nOther",
		},
		{
			fieldname: "min_residual_rating",
			label: __("Residual Rating At Least"),
			fieldtype: "Select",
			options: "\nLow\nMedium\nHigh\nCritical",
		},
		{
			fieldname: "include_drafts",
			label: __("Include Draft Assessments"),
			fieldtype: "Check",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && ["initial_rating", "residual_rating"].includes(column.fieldname)) {
			const c = RISK_REGISTER_COLORS[data[column.fieldname]];
			if (c) {
				value = `<span style="background:${c[0]};color:${c[1]};padding:1px 6px;border-radius:4px;font-weight:600">${value}</span>`;
			}
		}
		return value;
	},
};
