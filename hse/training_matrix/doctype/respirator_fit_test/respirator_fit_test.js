// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const PROTOCOLS = {
	"Qualitative (QLFT)": [
		"Isoamyl Acetate (banana oil)",
		"Saccharin",
		"Bitrex",
		"Irritant Smoke",
	],
	"Quantitative (QNFT)": [
		"Generated Aerosol",
		"Ambient Aerosol CNC (standard)",
		"Modified Ambient Aerosol CNC",
		"Controlled Negative Pressure (CNP)",
		"CNP REDON",
	],
};

frappe.ui.form.on("Respirator Fit Test", {
	refresh(frm) {
		frm.trigger("set_protocols");
	},
	test_type(frm) {
		frm.trigger("set_protocols");
		if (!(PROTOCOLS[frm.doc.test_type] || []).includes(frm.doc.protocol))
			frm.set_value("protocol", "");
	},
	set_protocols(frm) {
		const options = PROTOCOLS[frm.doc.test_type];
		frm.set_df_property(
			"protocol",
			"options",
			[""].concat(
				options || PROTOCOLS["Qualitative (QLFT)"].concat(PROTOCOLS["Quantitative (QNFT)"])
			)
		);
	},
	respirator_item(frm) {
		if (!frm.doc.respirator_item) return;
		frappe
			.call(
				"hse.training_matrix.doctype.respirator_fit_test.respirator_fit_test.item_details",
				{
					item: frm.doc.respirator_item,
				}
			)
			.then(({ message }) => {
				if (message && message.manufacturer)
					frm.set_value("manufacturer", message.manufacturer);
				if (message && message.model) frm.set_value("model", message.model);
			});
	},
});
