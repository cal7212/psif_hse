// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.ui.form.on("QC Inspection Template", {
	setup(frm) {
		frm.set_query("stage", () => ({ filters: { disabled: 0 }, order_by: "sequence asc" }));
	},
});
