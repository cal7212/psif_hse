// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.ui.form.on("Competency Evaluation", {
	setup(frm) {
		frm.set_query("checklist_template", () => ({
			filters: { training_requirement: frm.doc.training_requirement, disabled: 0 },
		}));
		frm.set_query("training_record", () => ({
			filters: { training_requirement: frm.doc.training_requirement, docstatus: 1 },
		}));
	},
	training_requirement(frm) {
		if (!frm.doc.training_requirement) return;
		frappe.db
			.get_value(
				"Competency Checklist Template",
				{ training_requirement: frm.doc.training_requirement, disabled: 0 },
				"name"
			)
			.then(({ message }) => {
				if (message && message.name) frm.set_value("checklist_template", message.name);
			});
	},
	checklist_template(frm) {
		if (!frm.doc.checklist_template) return;
		frappe
			.call(
				"hse.training_matrix.doctype.competency_evaluation.competency_evaluation.get_checklist",
				{ template: frm.doc.checklist_template }
			)
			.then(({ message }) => {
				frm.clear_table("checklist");
				(message || []).forEach((row) => frm.add_child("checklist", row));
				frm.refresh_field("checklist");
			});
	},
});
