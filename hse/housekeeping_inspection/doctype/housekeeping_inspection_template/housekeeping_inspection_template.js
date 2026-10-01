// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.ui.form.on("Housekeeping Inspection Template", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(
			__("Housekeeping Areas"),
			() => {
				frappe.set_route("List", "Housekeeping Area", { template: frm.doc.name });
			},
			__("View")
		);
	},
});
