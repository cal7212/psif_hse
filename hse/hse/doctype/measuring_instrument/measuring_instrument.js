// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.ui.form.on("Measuring Instrument", {
	refresh(frm) {
		if (frm.is_new()) return;
		const due = frm.doc.calibration_due;
		if (frm.doc.status !== "Active") {
			frm.dashboard.set_headline_alert(
				__("{0}: do not use for inspections.", [__(frm.doc.status)]),
				"red"
			);
		} else if (!frm.doc.calibration_required) {
			frm.dashboard.set_headline_alert(
				__("Verified before use; no calibration tracked."),
				"blue"
			);
		} else if (!due) {
			frm.dashboard.set_headline_alert(__("No calibration due date recorded."), "orange");
		} else if (frappe.datetime.get_diff(due, frappe.datetime.get_today()) < 0) {
			frm.dashboard.set_headline_alert(
				__("Calibration overdue since {0}.", [frappe.datetime.str_to_user(due)]),
				"red"
			);
		} else if (frappe.datetime.get_diff(due, frappe.datetime.get_today()) <= 30) {
			frm.dashboard.set_headline_alert(
				__("Calibration due {0}.", [frappe.datetime.str_to_user(due)]),
				"orange"
			);
		}
		frm.add_custom_button(__("Inspections Used On"), () => {
			frappe.set_route("query-report", "Instrument Usage", { instrument: frm.doc.name });
		});
	},
});
