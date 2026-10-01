// HPU Build Inspection follow-up on Non Conformance (loaded alongside non_conformance.js)
frappe.ui.form.on("Non Conformance", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.hpu_build_inspection) return;

		frm.add_custom_button(__("HPU Build Inspection"), () => {
			frappe.set_route("Form", "HPU Build Inspection", frm.doc.hpu_build_inspection);
		}, __("View"));
		if (frm.doc.hpu_unit) {
			frm.add_custom_button(__("HPU Unit"), () => {
				frappe.set_route("Form", "HPU Unit", frm.doc.hpu_unit);
			}, __("View"));
		}
		if (frm.doc.hpu_reinspection) {
			frm.add_custom_button(__("HPU Re-inspection"), () => {
				frappe.set_route("Form", "HPU Build Inspection", frm.doc.hpu_reinspection);
			}, __("View"));
		}
		if (frm.doc.status === "Open" && !frm.doc.hpu_reinspection) {
			frm.add_custom_button(__("HPU Re-inspection"), () => {
				frappe.call({
					method: "hse.hpu_build.doctype.hpu_build_inspection.hpu_build_inspection.make_reinspection_from_nc",
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
		if (frm.doc.status === "Open") {
			frm.dashboard.set_headline_alert(
				__("HPU {0} is on QC Hold until this Non Conformance is resolved.", [frm.doc.hpu_unit]),
				frm.doc.severity === "Critical" ? "red" : "orange"
			);
		}
	},
});
