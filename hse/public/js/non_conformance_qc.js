// Shop QC follow-up on Non Conformance (loaded alongside non_conformance.js)
frappe.ui.form.on("Non Conformance", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.qc_inspection) return;

		frm.add_custom_button(
			__("QC Inspection"),
			() => frappe.set_route("Form", "QC Inspection", frm.doc.qc_inspection),
			__("View")
		);
		if (frm.doc.qc_unit) {
			frm.add_custom_button(
				__("QC Unit"),
				() => frappe.set_route("Form", "QC Unit", frm.doc.qc_unit),
				__("View")
			);
		}
		if (frm.doc.qc_reinspection) {
			frm.add_custom_button(
				__("QC Re-inspection"),
				() => frappe.set_route("Form", "QC Inspection", frm.doc.qc_reinspection),
				__("View")
			);
		}
		if (frm.doc.status === "Open" && !frm.doc.qc_reinspection) {
			frm.add_custom_button(
				__("QC Re-inspection"),
				() => {
					frappe.call({
						method: "hse.shop_qc.doctype.qc_inspection.qc_inspection.make_reinspection_from_nc",
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
		if (frm.doc.status === "Open") {
			frm.dashboard.set_headline_alert(
				__("{0} is on QC Hold until this Non Conformance is resolved.", [frm.doc.qc_unit]),
				frm.doc.severity === "Critical" ? "red" : "orange"
			);
		}
	},
});
