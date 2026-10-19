// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.ui.form.on("Training Requirement", {
	refresh(frm) {
		if (
			frm.doc.materials_review_due &&
			frm.doc.materials_review_due < frappe.datetime.get_today()
		) {
			frm.dashboard.set_headline_alert(
				__("Training materials are past their 2-year review (TRN-700 §4.14)."),
				"orange"
			);
		}
		if (!frm.is_new()) {
			frm.add_custom_button(__("Employees"), () =>
				frappe.set_route("query-report", "Training Matrix", {
					training_requirement: frm.doc.name,
				})
			);
		}
	},
	all_employees(frm) {
		if (frm.doc.all_employees) {
			frappe.show_alert({
				message: __(
					"Required for every active employee; the role table is for reference."
				),
				indicator: "blue",
			});
		}
	},
});
