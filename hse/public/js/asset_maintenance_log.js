frappe.ui.form.on("Asset Maintenance Log", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.asset_inspection) {
			frm.add_custom_button(__("Asset Inspection"), () => {
				frappe.set_route("Form", "Asset Inspection", frm.doc.asset_inspection);
			}, __("View"));
		}

		if (frm.doc.docstatus === 0 && frm.doc.maintenance_status !== "Completed") {
			frm.add_custom_button(__("Asset Inspection"), () => {
				frappe.model.open_mapped_doc({
					method: "hse.asset_inspection.doctype.asset_inspection.asset_inspection.make_from_maintenance_log",
					frm,
				});
			}, __("Create"));
			frm.page.set_inner_btn_group_as_primary(__("Create"));
		}
	},
});
