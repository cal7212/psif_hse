// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.ui.form.on("OSHA 300A Summary", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("OSHA 300 Log"), () =>
				frappe.set_route("query-report", "OSHA 300 Log", { year: frm.doc.year })
			);
		}
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			frm.add_custom_button(__("Recalculate Totals"), () => frm.save());
		}
		if (frm.doc.cases_missing_type) {
			frm.dashboard.set_headline_alert(
				__("{0} recordable case(s) are missing an injury/illness type.", [frm.doc.cases_missing_type]),
				"orange"
			);
		}
	},
	year(frm) {
		if (frm.doc.year && !frm.doc.annual_average_employees) {
			frm.set_intro(__("Totals are calculated from submitted, recordable Injury_Illness Reports when you save."), "blue");
		}
	},
});
