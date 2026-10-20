// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.ui.form.on("Document Revision", {
	document_number(frm) {
		if (!frm.doc.document_number || frm.doc.docstatus) return;
		frappe
			.call("hse.training_matrix.doctype.document_revision.document_revision.get_courses", {
				document_number: frm.doc.document_number,
			})
			.then(({ message }) => {
				frm.clear_table("courses");
				(message || []).forEach((row) => frm.add_child("courses", row));
				frm.refresh_field("courses");
				if (!(message || []).length) {
					frappe.show_alert({
						message: __("No courses list {0} as their document.", [
							frm.doc.document_number,
						]),
						indicator: "orange",
					});
				}
			});
	},
});

frappe.ui.form.on("Document Revision Course", {
	retraining(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.retraining !== "No Retraining" && !row.due_date) {
			frappe.model.set_value(
				cdt,
				cdn,
				"due_date",
				frappe.datetime.add_days(frm.doc.effective_date, 30)
			);
		}
	},
});
