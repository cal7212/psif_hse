// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

// Shared by Confined Space Permit and Energized Electrical Work Permit (hooks.py doctype_js).
// Server side: hse/hse/permits.py.
frappe.provide("hse.permits");

window.hse.permits.refresh = function (frm, open_status, end_field) {
	if (frm.doc.docstatus !== 1 || frm.doc.status !== open_status) return;
	if (frm.doc[end_field] && frappe.datetime.str_to_obj(frm.doc[end_field]) < new Date()) {
		frm.set_intro(__("The authorized period has ended. Close the permit."), "red");
	}
	frm.add_custom_button(__("Close Permit"), () => window.hse.permits.close_dialog(frm)).addClass(
		"btn-primary"
	);
};

window.hse.permits.close_dialog = function (frm) {
	const d = new frappe.ui.Dialog({
		title: __("Close Permit"),
		fields: [
			{
				fieldname: "reason",
				fieldtype: "Select",
				label: __("Reason"),
				options: ["Work Completed", "Prohibited Condition", "Permit Expired"],
				default: "Work Completed",
				reqd: 1,
			},
			{
				fieldname: "notes",
				fieldtype: "Small Text",
				label: __("Notes"),
				mandatory_depends_on: "eval:doc.reason=='Prohibited Condition'",
				description: __("For a prohibited condition: what happened and what was done."),
			},
		],
		primary_action_label: __("Close Permit"),
		primary_action(values) {
			frappe
				.call({
					method: "hse.hse.permits.close_permit",
					args: {
						doctype: frm.doctype,
						name: frm.doc.name,
						reason: values.reason,
						notes: values.notes,
					},
					freeze: true,
				})
				.then(() => {
					d.hide();
					frm.reload_doc();
				});
		},
	});
	d.show();
};

window.hse.permits.indicator = function (doc, open_status, end_field) {
	if (doc.docstatus === 0) return [__("Draft"), "gray", "docstatus,=,0"];
	if (doc.status === "Cancelled") return [__("Cancelled"), "red", "status,=,Cancelled"];
	if (doc.status === "Closed") return [__("Closed"), "darkgrey", "status,=,Closed"];
	if (doc[end_field] && frappe.datetime.str_to_obj(doc[end_field]) < new Date()) {
		return [__("Expired – Close"), "red", `status,=,${open_status}`];
	}
	return [__(open_status), "green", `status,=,${open_status}`];
};
