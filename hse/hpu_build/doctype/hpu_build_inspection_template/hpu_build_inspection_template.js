frappe.ui.form.on("HPU Build Inspection Template", {
	setup(frm) {
		frm.set_query("stage", () => ({ filters: { disabled: 0 } }));
	},
});
