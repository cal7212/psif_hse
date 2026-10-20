// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const TM_REQUESTS = "hse.training_matrix.training_requests";

frappe.ui.form.on("Training Request", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.status === "Pending") {
			["Approved", "Rejected"].forEach((decision) =>
				frm.add_custom_button(
					decision === "Approved" ? __("Approve") : __("Reject"),
					() =>
						frappe.prompt(
							{ fieldname: "notes", label: __("Notes"), fieldtype: "Small Text" },
							(values) =>
								frappe
									.call(`${TM_REQUESTS}.decide_training_request`, {
										name: frm.doc.name,
										decision,
										notes: values.notes,
									})
									.then(() => frm.reload_doc()),
							decision === "Approved" ? __("Approve request") : __("Reject request")
						),
					__("Decision")
				)
			);
		}
		if (frm.doc.status === "Approved") {
			frm.add_custom_button(__("Mark Completed"), () =>
				frappe.prompt(
					{
						fieldname: "completed_on",
						label: __("Completed On"),
						fieldtype: "Date",
						reqd: 1,
						default: frappe.datetime.get_today(),
					},
					(values) =>
						frappe
							.call(`${TM_REQUESTS}.complete_training_request`, {
								name: frm.doc.name,
								completed_on: values.completed_on,
							})
							.then(() => frm.reload_doc())
				)
			);
		}
	},
});
