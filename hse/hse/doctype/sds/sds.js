// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const SDS_METHOD = "hse.hse.doctype.sds.sds";

frappe.ui.form.on("SDS", {
	setup(frm) {
		frm.set_query("supersedes", () => ({
			filters: { name: ["!=", frm.doc.name], superseded_by: ["is", "not set"] },
		}));
		frm.set_query("location", "locations", () => ({ filters: { is_group: 0 } }));
	},

	refresh(frm) {
		const colors = { Active: "green", Superseded: "gray", Discontinued: "orange" };
		if (!frm.is_new()) frm.page.set_indicator(__(frm.doc.status), colors[frm.doc.status] || "gray");

		if (frm.doc.sds_uploaded) {
			frm.dashboard.set_headline_alert(__("A new or updated SDS has been requested for this product."), "orange");
		}
		if (frm.doc.status === "Active" && !frm.doc.attach_sds && !frm.is_new()) {
			frm.dashboard.set_headline_alert(__("No SDS attached. Employees cannot view it."), "red");
		}

		if (frm.is_new()) return;

		if (frm.doc.attach_sds) {
			frm.add_custom_button(__("Open SDS"), () => window.open(frm.doc.attach_sds, "_blank"));
		}

		if (frm.doc.status === "Active" && !frm.doc.superseded_by) {
			frm.add_custom_button(__("New Version"), () => {
				frappe.call({
					method: `${SDS_METHOD}.make_new_version`,
					args: { source_name: frm.doc.name },
					freeze: true,
					callback: (r) => {
						if (!r.message) return;
						const doc = frappe.model.sync(r.message)[0];
						frappe.set_route("Form", doc.doctype, doc.name);
					},
				});
			}, __("Create"));

			frm.add_custom_button(__("Mark Reviewed"), () => {
				frappe.call({
					method: `${SDS_METHOD}.mark_reviewed`,
					args: { name: frm.doc.name },
					freeze: true,
					callback: () => frm.reload_doc(),
				});
			});
		}

		if (frm.doc.superseded_by) {
			frm.add_custom_button(__("Current Version"), () => frappe.set_route("Form", "SDS", frm.doc.superseded_by), __("View"));
		}
		if (frm.doc.supersedes) {
			frm.add_custom_button(__("Previous Version"), () => frappe.set_route("Form", "SDS", frm.doc.supersedes), __("View"));
		}
		frm.add_custom_button(__("SDS Inventory"), () => frappe.set_route("query-report", "SDS Inventory"), __("View"));
	},

	status(frm) {
		if (frm.doc.status === "Discontinued" && !frm.doc.discontinued_date) {
			frm.set_value("discontinued_date", frappe.datetime.get_today());
		}
	},
});
