// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const HBI_METHOD = "hse.hpu_build.doctype.hpu_build_inspection.hpu_build_inspection";
const HPU_UTILS = "hse.hpu_build.utils";

frappe.ui.form.on("HPU Build Inspection", {
	setup(frm) {
		frm.ignore_doctypes_on_cancel_all = ["Non Conformance", "HPU Build Inspection", "HPU Unit"];

		frm.set_query("hpu_unit", () => ({
			filters: { status: ["not in", ["Shipped", "Cancelled"]] },
		}));
		frm.set_query("stage", () => ({ filters: { disabled: 0 }, order_by: "sequence asc" }));
		frm.set_query("template", () => ({
			filters: { disabled: 0, stage: frm.doc.stage || "" },
		}));
		frm.set_query("reinspection_of", () => ({
			filters: {
				hpu_unit: frm.doc.hpu_unit, stage: frm.doc.stage,
				docstatus: 1, status: "Rejected", name: ["!=", frm.doc.name],
			},
		}));
	},

	onload(frm) {
		if (frm.is_new() && !frm.doc.inspected_by) {
			frappe.db.get_value("Employee", { user_id: frappe.session.user }, "name").then((r) => {
				if (r.message && r.message.name) frm.set_value("inspected_by", r.message.name);
			});
		}
	},

	refresh(frm) {
		frm.trigger("set_indicator");
		frm.trigger("render_instructions");

		if (frm.doc.docstatus === 1 && frm.doc.status === "Rejected") {
			frm.add_custom_button(__("Re-inspection"), () => {
				frappe.model.open_mapped_doc({ method: `${HBI_METHOD}.make_reinspection`, frm });
			}, __("Create"));
		}
		if (frm.doc.non_conformance) {
			frm.add_custom_button(__("Non Conformance"), () => {
				frappe.set_route("Form", "Non Conformance", frm.doc.non_conformance);
			}, __("View"));
		}
		if (frm.doc.hpu_unit) {
			frm.add_custom_button(__("HPU Unit"), () => {
				frappe.set_route("Form", "HPU Unit", frm.doc.hpu_unit);
			}, __("View"));
		}
		if (frm.doc.docstatus === 0 && frm.doc.template) {
			frm.add_custom_button(__("Mark All Pass"), () => {
				(frm.doc.items || []).forEach((row) => {
					// Only plain pass/fail checks; numeric, text and photo items need real input.
					if (!row.result && !row.numeric && !row.record_text && !row.requires_photo) {
						frappe.model.set_value(row.doctype, row.name, "result", "Pass");
					}
				});
			});
			frm.add_custom_button(__("Reload Checklist"), () => frm.trigger("load_items"));
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
			method: `${HBI_METHOD}.get_template_instructions`,
			args: { template: frm.doc.template },
			callback: (r) => {
				if (r.message) {
					wrapper.html(`<div class="alert alert-info" style="margin-bottom:10px">${r.message}</div>`);
				}
			},
		});
	},

	hpu_unit(frm) {
		if (!frm.doc.hpu_unit || frm.doc.is_reinspection) return;
		frappe.call({
			method: `${HPU_UTILS}.get_next_stage`,
			args: { hpu_unit: frm.doc.hpu_unit },
			callback: (r) => {
				if (r.message && !frm.doc.stage) frm.set_value("stage", r.message);
				else if (frm.doc.template) frm.trigger("load_items");
			},
		});
	},

	stage(frm) {
		frm.set_value("template", null);
		if (!frm.doc.stage) return;
		// fetch_from on model runs async; read it straight from the unit
		frappe.db.get_value("HPU Unit", frm.doc.hpu_unit, "model").then((r) => {
			frappe.call({
				method: `${HPU_UTILS}.get_default_template`,
				args: { stage: frm.doc.stage, model: (r.message && r.message.model) || "" },
				callback: (t) => { if (t.message) frm.set_value("template", t.message); },
			});
		});
	},

	template(frm) {
		frm.trigger("render_instructions");
		frm.trigger("load_items");
	},

	load_items(frm) {
		frm.clear_table("items");
		frm.refresh_field("items");
		if (!frm.doc.template) return;
		frappe.call({
			method: `${HBI_METHOD}.get_template_items`,
			args: { template: frm.doc.template, hpu_unit: frm.doc.hpu_unit },
			callback: (r) => {
				(r.message || []).forEach((item) => Object.assign(frm.add_child("items"), item));
				frm.refresh_field("items");
			},
		});
	},

	is_reinspection(frm) {
		if (!frm.doc.is_reinspection) frm.set_value("reinspection_of", null);
	},
});

frappe.ui.form.on("HPU Build Inspection Reading", {
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
				message: __("Critical item failed: {0}. A Critical Non Conformance will be raised on submit.", [row.check_item]),
				indicator: "red",
			});
		}
	},
});
