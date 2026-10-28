// QC Unit: issue shop supplies against this unit's work order.
frappe.ui.form.on("QC Unit", {
	refresh(frm) {
		if (frm.is_new() || !frappe.model.can_create("Stock Entry")) return;
		frm.add_custom_button(
			__("Issue Supplies"),
			() =>
				window.hse.supplies.issue({
					qc_unit: frm.doc.name,
					after_issue: () => frm.reload_doc(),
				}),
			__("Create")
		);
	},
});
