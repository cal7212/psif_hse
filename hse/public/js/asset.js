frappe.ui.form.on("Asset", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.safety_status === "Out of Service") {
			frm.dashboard.set_headline_alert(
				__("Out of Service: open critical Non Conformance. Do not operate."),
				"red"
			);
			frm.add_custom_button(__("Open Non Conformances"), () => {
				frappe.set_route("List", "Non Conformance", { asset: frm.doc.name, status: "Open" });
			}, __("View"));
		}

		frm.add_custom_button(__("Asset Inspections"), () => {
			frappe.set_route("List", "Asset Inspection", { asset: frm.doc.name });
		}, __("View"));

		frm.add_custom_button(__("Asset Inspection"), () => {
			frappe.new_doc("Asset Inspection", { asset: frm.doc.name });
		}, __("Create"));
	},
});
