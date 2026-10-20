// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt
// Training Matrix: "Retraining Required" on incidents and NCR / CAPA (TRN-700 Rev 1 §4.10).

const TM_RETRAINING_TRIGGER = {
	"Injury_Illness Report": {
		reason_type: "Incident or Near Miss",
		employee_fields: ["employee_name"],
	},
	"Non Conformance": { reason_type: "Nonconformance or CAPA", employee_fields: [] },
};

Object.keys(TM_RETRAINING_TRIGGER).forEach((doctype) => {
	frappe.ui.form.on(doctype, {
		refresh(frm) {
			if (frm.is_new() || !frappe.model.can_create("Retraining Assignment")) return;
			frm.add_custom_button(
				__("Retraining Required"),
				() => tm_new_retraining(frm, TM_RETRAINING_TRIGGER[doctype]),
				__("Create")
			);
		},
	});
});

function tm_new_retraining(frm, trigger) {
	frappe.model.with_doctype("Retraining Assignment", () => {
		const doc = frappe.model.get_new_doc("Retraining Assignment");
		doc.reason_type = trigger.reason_type;
		doc.reference_doctype = frm.doctype;
		doc.reference_name = frm.doc.name;
		doc.reason = __("Retraining required following {0} {1}.", [__(frm.doctype), frm.doc.name]);
		trigger.employee_fields
			.map((field) => frm.doc[field])
			.filter(Boolean)
			.forEach((employee) => {
				frappe.model.add_child(doc, "employees").employee = employee;
			});
		frappe.set_route("Form", doc.doctype, doc.name);
	});
}
