// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const AI_METHOD = "hse.asset_inspection.doctype.asset_inspection.asset_inspection";

frappe.ui.form.on("Asset Inspection", {
	setup(frm) {
		// Cancelling an inspection must NOT offer to cancel the submitted
		// Maintenance Log or other records that link back to it.
		frm.ignore_doctypes_on_cancel_all = ["Asset Maintenance Log", "Non Conformance", "Asset Inspection"];

		// Show templates for this asset's category plus general (no category) templates
		frm.set_query("template", () => {
			const q = { filters: [["disabled", "=", 0]] };
			if (frm.doc.asset_category) {
				q.or_filters = [
					["asset_category", "=", frm.doc.asset_category],
					["asset_category", "is", "not set"],
				];
			}
			return q;
		});
		frm.set_query("asset_maintenance_log", () => ({
			filters: { asset_name: frm.doc.asset, docstatus: 0 },
		}));
		frm.set_query("reinspection_of", () => ({
			filters: { asset: frm.doc.asset, docstatus: 1, status: "Rejected", name: ["!=", frm.doc.name] },
		}));
	},

	refresh(frm) {
		frm.trigger("set_indicator");
		frm.trigger("render_instructions");

		if (frm.doc.docstatus === 1 && frm.doc.status === "Rejected") {
			frm.add_custom_button(__("Re-inspection"), () => {
				frappe.model.open_mapped_doc({ method: `${AI_METHOD}.make_reinspection`, frm });
			}, __("Create"));
		}
		if (frm.doc.non_conformance) {
			frm.add_custom_button(__("Non Conformance"), () => {
				frappe.set_route("Form", "Non Conformance", frm.doc.non_conformance);
			}, __("View"));
		}
		if (frm.doc.docstatus === 0 && frm.doc.template) {
			frm.add_custom_button(__("Mark All Pass"), () => {
				(frm.doc.items || []).forEach((row) => {
					if (!row.result && !row.numeric) {
						frappe.model.set_value(row.doctype, row.name, "result", "Pass");
					}
				});
			});
		}
	},

	set_indicator(frm) {
		const colors = { Pending: "orange", Accepted: "green", Rejected: "red" };
		if (frm.doc.docstatus === 1 && frm.doc.status) {
			frm.page.set_indicator(__(frm.doc.status), colors[frm.doc.status] || "gray");
		}
	},

	render_instructions(frm) {
		const wrapper = frm.get_field("instructions").$wrapper;
		wrapper.empty();
		if (!frm.doc.template) return;
		frappe.call({
			method: `${AI_METHOD}.get_template_instructions`,
			args: { template: frm.doc.template },
			callback: (r) => {
				if (r.message) {
					wrapper.html(`<div class="alert alert-info" style="margin-bottom:10px">${r.message}</div>`);
				}
			},
		});
	},

	asset(frm) {
		if (frm.doc.template && frm.doc.asset_category) {
			frappe.db.get_value("Asset Inspection Template", frm.doc.template, "asset_category").then((r) => {
				const cat = r.message && r.message.asset_category;
				if (cat && cat !== frm.doc.asset_category) frm.set_value("template", null);
			});
		}
	},

	template(frm) {
		frm.clear_table("items");
		frm.refresh_field("items");
		frm.trigger("render_instructions");
		if (!frm.doc.template) return;
		frappe.call({
			method: `${AI_METHOD}.get_template_items`,
			args: { template: frm.doc.template },
			callback: (r) => {
				(r.message || []).forEach((item) => {
					const row = frm.add_child("items");
					Object.assign(row, item);
				});
				frm.refresh_field("items");
			},
		});
	},

	is_reinspection(frm) {
		if (!frm.doc.is_reinspection) frm.set_value("reinspection_of", null);
	},
});

frappe.ui.form.on("Asset Inspection Reading", {
	reading_value(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.numeric || row.result === "N/A") return;
		if (row.reading_value === null || row.reading_value === undefined || row.reading_value === "") return;
		const v = flt(row.reading_value);
		const ok = (!row.min_value || v >= flt(row.min_value)) && (!row.max_value || v <= flt(row.max_value));
		frappe.model.set_value(cdt, cdn, "result", ok ? "Pass" : "Fail");
	},

	result(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.result === "Fail" && row.is_critical) {
			frappe.show_alert({
				message: __("Critical item failed: {0}. The asset will be placed Out of Service on submit.", [row.check_item]),
				indicator: "red",
			});
		}
	},
});
