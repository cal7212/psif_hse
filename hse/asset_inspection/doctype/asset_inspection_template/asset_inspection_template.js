frappe.ui.form.on("Asset Inspection Template", {
	refresh(frm) {
		if (!frm.is_new() && !frm.doc.disabled) {
			frm.add_custom_button(
				__("Asset Inspection"),
				() => {
					frappe.new_doc("Asset Inspection", { template: frm.doc.name });
				},
				__("Create")
			);
		}
	},
});
