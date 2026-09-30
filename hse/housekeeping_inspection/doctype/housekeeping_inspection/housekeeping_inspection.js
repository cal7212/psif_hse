// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const HKI_METHOD = "hse.housekeeping_inspection.doctype.housekeeping_inspection.housekeeping_inspection";

frappe.ui.form.on("Housekeeping Inspection", {
	setup(frm) {
		frm.set_query("housekeeping_area", () => ({ filters: { disabled: 0 } }));
		frm.set_query("template", () => ({ filters: { disabled: 0 } }));
		frm.set_query("reinspection_of", () => ({
			filters: {
				housekeeping_area: frm.doc.housekeeping_area,
				docstatus: 1,
				status: "Rejected",
				name: ["!=", frm.doc.name],
			},
		}));
	},

	refresh(frm) {
		frm.trigger("set_indicator");
		frm.trigger("render_instructions");

		if (frm.doc.docstatus === 1 && frm.doc.status === "Rejected") {
			frm.add_custom_button(__("Re-inspection"), () => {
				frappe.model.open_mapped_doc({ method: `${HKI_METHOD}.make_reinspection`, frm });
			}, __("Create"));
		}
		if (frm.doc.non_conformance) {
			frm.add_custom_button(__("Non Conformance"), () => {
				frappe.set_route("Form", "Non Conformance", frm.doc.non_conformance);
			}, __("View"));
		}
		if (frm.doc.docstatus === 0 && frm.doc.template) {
			frm.add_custom_button(__("Mark Remaining Pass"), () => {
				(frm.doc.items || []).forEach((row) => {
					if (!row.result) frappe.model.set_value(row.doctype, row.name, "result", "Pass");
				});
			});
		}
	},

	set_indicator(frm) {
		const colors = { Pending: "orange", Accepted: "green", Rejected: "red" };
		if (frm.doc.docstatus === 1 && frm.doc.status) {
			frm.page.set_indicator(
				`${__(frm.doc.status)} (${flt(frm.doc.score, 1)}%)`,
				colors[frm.doc.status] || "gray"
			);
		}
	},

	render_instructions(frm) {
		const wrapper = frm.get_field("instructions").$wrapper;
		wrapper.empty();
		if (!frm.doc.template) return;
		frappe.call({
			method: `${HKI_METHOD}.get_template_instructions`,
			args: { template: frm.doc.template },
			callback: (r) => {
				if (r.message) {
					wrapper.html(`<div class="alert alert-info" style="margin-bottom:10px">${r.message}</div>`);
				}
			},
		});
	},

	housekeeping_area(frm) {
		if (!frm.doc.housekeeping_area) return;
		frappe.db.get_value("Housekeeping Area", frm.doc.housekeeping_area, "template").then((r) => {
			const t = r.message && r.message.template;
			if (t && t !== frm.doc.template) frm.set_value("template", t);
		});
	},

	template(frm) {
		frm.clear_table("items");
		frm.refresh_field("items");
		frm.trigger("render_instructions");
		if (!frm.doc.template) return;
		frappe.call({
			method: `${HKI_METHOD}.get_template_items`,
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

frappe.ui.form.on("Housekeeping Inspection Item", {
	result(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.result !== "Fail") {
			if (row.corrected_on_spot) frappe.model.set_value(cdt, cdn, "corrected_on_spot", 0);
			return;
		}
		if (row.is_critical) {
			frappe.show_alert({
				message: __(
					"Critical item failed: {0}. Correct it now and tick Corrected on the Spot, or a Critical Non Conformance will be raised on submit.",
					[row.check_item]
				),
				indicator: "red",
			});
		}
	},
});
