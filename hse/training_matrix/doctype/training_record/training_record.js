// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.ui.form.on("Training Record", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		frm.add_custom_button(__("Competency Evaluation"), () => {
			const pending = (frm.doc.attendees || []).filter((r) => r.result !== "Fail");
			const open = (employee) =>
				frappe.new_doc("Competency Evaluation", {
					employee,
					training_requirement: frm.doc.training_requirement,
					training_record: frm.doc.name,
				});
			if (pending.length === 1) return open(pending[0].employee);
			frappe.prompt(
				{
					fieldname: "employee",
					label: __("Attendee"),
					fieldtype: "Select",
					options: pending.map((r) => r.employee),
					reqd: 1,
				},
				(values) => open(values.employee),
				__("Evaluate an attendee")
			);
		});
	},
});
