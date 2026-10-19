// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const TM_STATUS_COLORS = {
	Completed: "green",
	"In Progress": "blue",
	Due: "orange",
	Overdue: "red",
	"Not Started": "gray",
	"Confirm Applicability": "purple",
	"Not Applicable": "light-gray",
};

frappe.ui.form.on("Employee Training Matrix", {
	setup(frm) {
		frm.set_indicator_formatter(
			"training_requirement",
			(doc) => TM_STATUS_COLORS[doc.status] || "gray"
		);
	},

	refresh(frm) {
		if (frm.is_new()) return;
		if (!frm.doc.active) {
			frm.dashboard.set_headline_alert(
				__("Employee is not active. The matrix is kept for the record."),
				"gray"
			);
		} else if (frm.doc.overdue_count) {
			frm.dashboard.set_headline_alert(
				__(
					"{0} required course(s) overdue. Escalate to the Manager and HR Manager (TRN-700 §4.9).",
					[frm.doc.overdue_count]
				),
				"red"
			);
		} else if (frm.doc.confirm_count) {
			frm.dashboard.set_headline_alert(
				__("{0} conditional course(s) need the Manager to confirm whether they apply.", [
					frm.doc.confirm_count,
				]),
				"purple"
			);
		}
		if (frm.doc.no_lms_login) {
			frm.dashboard.add_comment(
				__("This employee has no user login, so training cannot be completed in the LMS."),
				"orange",
				true
			);
		}
		if (frappe.user.has_role(["System Manager", "HR Manager", "Training Coordinator"])) {
			frm.add_custom_button(__("Sync from HR"), () =>
				frappe
					.call({
						method: "hse.training_matrix.matrix.sync_employee_matrix",
						args: { employee: frm.doc.employee },
						freeze: true,
					})
					.then(() => frm.reload_doc())
			);
		}
		frm.add_custom_button(__("Training Matrix Report"), () =>
			frappe.set_route("query-report", "Training Matrix", { employee: frm.doc.employee })
		);
	},
});
