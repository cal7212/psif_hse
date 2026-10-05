// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.ui.form.on("QC Document Template", {
	refresh(frm) {
		if (frm.doc.is_default) {
			frm.set_intro(
				__("Loaded automatically on new {0} units.", [
					frm.doc.product_type || __("Power Unit, Manifold and Valve Stand"),
				]),
				"blue"
			);
		}
	},
});
