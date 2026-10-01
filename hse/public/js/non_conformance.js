frappe.ui.form.on("Non Conformance", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (frm.doc.asset_inspection) frm.trigger("setup_asset_inspection");
		if (frm.doc.housekeeping_inspection) frm.trigger("setup_housekeeping_inspection");
	},

	setup_asset_inspection(frm) {
		frm.add_custom_button(
			__("Original Inspection"),
			() => {
				frappe.set_route("Form", "Asset Inspection", frm.doc.asset_inspection);
			},
			__("View")
		);

		if (frm.doc.reinspection) {
			frm.add_custom_button(
				__("Re-inspection"),
				() => {
					frappe.set_route("Form", "Asset Inspection", frm.doc.reinspection);
				},
				__("View")
			);
		}

		if (frm.doc.status === "Open" && !frm.doc.reinspection) {
			frm.add_custom_button(
				__("Re-inspection"),
				() => {
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
				},
				__("Create")
			);
		}

		if (frm.doc.severity === "Critical" && frm.doc.status === "Open") {
			frm.dashboard.set_headline_alert(
				__("Asset {0} is Out of Service until this Non Conformance is resolved.", [
					frm.doc.asset,
				]),
				"red"
			);
		}
	},

	setup_housekeeping_inspection(frm) {
		frm.add_custom_button(
			__("Housekeeping Inspection"),
			() => {
				frappe.set_route(
					"Form",
					"Housekeeping Inspection",
					frm.doc.housekeeping_inspection
				);
			},
			__("View")
		);

		if (frm.doc.housekeeping_reinspection) {
			frm.add_custom_button(
				__("Housekeeping Re-inspection"),
				() => {
					frappe.set_route(
						"Form",
						"Housekeeping Inspection",
						frm.doc.housekeeping_reinspection
					);
				},
				__("View")
			);
		}

		if (frm.doc.status === "Open" && !frm.doc.housekeeping_reinspection) {
			frm.add_custom_button(
				__("Housekeeping Re-inspection"),
				() => {
					frappe.call({
						method: "hse.housekeeping_inspection.doctype.housekeeping_inspection.housekeeping_inspection.make_reinspection_from_nc",
						args: { non_conformance: frm.doc.name },
						freeze: true,
						callback: (r) => {
							if (!r.message) return;
							const doc = frappe.model.sync(r.message)[0];
							frappe.set_route("Form", doc.doctype, doc.name);
						},
					});
				},
				__("Create")
			);
		}

		if (frm.doc.severity === "Critical" && frm.doc.status === "Open") {
			frm.dashboard.set_headline_alert(
				__(
					"Critical housekeeping hazard open in {0}. Keep the interim control in place until resolved.",
					[frm.doc.housekeeping_area]
				),
				"red"
			);
		}
	},
});
