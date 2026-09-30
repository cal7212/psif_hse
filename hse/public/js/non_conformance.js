frappe.ui.form.on("Non Conformance", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.asset_inspection) return;

		frm.add_custom_button(__("Original Inspection"), () => {
			frappe.set_route("Form", "Asset Inspection", frm.doc.asset_inspection);
		}, __("View"));

		if (frm.doc.reinspection) {
			frm.add_custom_button(__("Re-inspection"), () => {
				frappe.set_route("Form", "Asset Inspection", frm.doc.reinspection);
			}, __("View"));
		}

		if (frm.doc.status === "Open" && !frm.doc.reinspection) {
			frm.add_custom_button(__("Re-inspection"), () => {
				frappe.call({
					method: "hse.asset_inspection.doctype.asset_inspection.asset_inspection.make_reinspection_from_nc",
					args: { non_conformance: frm.doc.name },
					freeze: true,
					callback: (r) => {
						if (!r.message) return;
						const doc = frappe.model.sync(r.message)[0];
						frappe.set_route("Form", doc.doctype, doc.name);
					},
				});
			}, __("Create"));
		}

		if (frm.doc.severity === "Critical" && frm.doc.status === "Open") {
			frm.dashboard.set_headline_alert(
				__("Asset {0} is Out of Service until this Non Conformance is resolved.", [frm.doc.asset]),
				"red"
			);
		}
	},
});
