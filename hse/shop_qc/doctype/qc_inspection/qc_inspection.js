// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const QCI_METHOD = "hse.shop_qc.doctype.qc_inspection.qc_inspection";
const QC_UTILS = "hse.shop_qc.utils";

frappe.ui.form.on("QC Inspection", {
	setup(frm) {
		frm.ignore_doctypes_on_cancel_all = ["Non Conformance", "QC Inspection", "QC Unit"];

		frm.set_query("qc_unit", () => ({
			filters: { status: ["not in", ["Shipped", "Cancelled"]] },
		}));
		frm.set_query("stage", () => ({
			filters: { disabled: 0, name: ["in", frm._applicable_stages || []] },
			order_by: "sequence asc",
		}));
		frm.set_query("template", () => ({
			filters: {
				disabled: 0,
				stage: frm.doc.stage || "",
				product_type: ["in", ["", frm.doc.product_type || ""]],
			},
		}));
		frm.set_query("reinspection_of", () => ({
			filters: {
				qc_unit: frm.doc.qc_unit,
				stage: frm.doc.stage,
				docstatus: 1,
				status: "Rejected",
				name: ["!=", frm.doc.name],
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
		frm.trigger("load_applicable_stages");
		frm.trigger("set_indicator");
		frm.trigger("render_instructions");

		if (frm.doc.docstatus === 1 && frm.doc.status === "Rejected") {
			frm.add_custom_button(
				__("Re-inspection"),
				() => {
					frappe.model.open_mapped_doc({
						method: `${QCI_METHOD}.make_reinspection`,
						frm,
					});
				},
				__("Create")
			);
		}
		if (frm.doc.non_conformance) {
			frm.add_custom_button(
				__("Non Conformance"),
				() => {
					frappe.set_route("Form", "Non Conformance", frm.doc.non_conformance);
				},
				__("View")
			);
		}
		if (frm.doc.qc_unit) {
			frm.add_custom_button(
				__("QC Unit"),
				() => {
					frappe.set_route("Form", "QC Unit", frm.doc.qc_unit);
				},
				__("View")
			);
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

	load_applicable_stages(frm) {
		if (!frm.doc.qc_unit) {
			frm._applicable_stages = [];
			return;
		}
		frappe
			.xcall(`${QC_UTILS}.get_applicable_stages`, { qc_unit: frm.doc.qc_unit })
			.then((stages) => (frm._applicable_stages = stages || []));
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
			method: `${QCI_METHOD}.get_template_instructions`,
			args: { template: frm.doc.template },
			callback: (r) => {
				if (r.message) {
					wrapper.html(
						`<div class="alert alert-info" style="margin-bottom:10px">${r.message}</div>`
					);
				}
			},
		});
	},

	qc_unit(frm) {
		frm.trigger("load_applicable_stages");
		if (!frm.doc.qc_unit || frm.doc.is_reinspection) return;
		frappe.call({
			method: `${QC_UTILS}.get_next_stage`,
			args: { qc_unit: frm.doc.qc_unit },
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
		frappe.db.get_value("QC Unit", frm.doc.qc_unit, ["model", "product_type"]).then((r) => {
			const unit = r.message || {};
			frappe.call({
				method: `${QC_UTILS}.get_default_template`,
				args: {
					stage: frm.doc.stage,
					model: unit.model || "",
					product_type: unit.product_type || "",
				},
				callback: (t) => {
					if (t.message) frm.set_value("template", t.message);
				},
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
			method: `${QCI_METHOD}.get_template_items`,
			args: { template: frm.doc.template, qc_unit: frm.doc.qc_unit },
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

frappe.ui.form.on("QC Inspection Reading", {
	reading_value(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.numeric || row.result === "N/A") return;
		if (
			row.reading_value === null ||
			row.reading_value === undefined ||
			row.reading_value === ""
		)
			return;
		const v = flt(row.reading_value);
		const ok =
			(!row.min_value || v >= flt(row.min_value)) &&
			(!row.max_value || v <= flt(row.max_value));
		frappe.model.set_value(cdt, cdn, "result", ok ? "Pass" : "Fail");
	},

	result(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.result === "Fail" && row.is_critical) {
			frappe.show_alert({
				message: __(
					"Critical item failed: {0}. A Critical Non Conformance will be raised on submit.",
					[row.check_item]
				),
				indicator: "red",
			});
		}
	},
});

frappe.ui.form.on("QC Hose Test", {
	crimp_a: (frm, cdt, cdn) => evaluate_hose_row(cdt, cdn, "crimp_a"),
	crimp_b: (frm, cdt, cdn) => evaluate_hose_row(cdt, cdn, "crimp_b"),
	pressure_reached: (frm, cdt, cdn) => evaluate_hose_row(cdt, cdn),
	hold_actual_min: (frm, cdt, cdn) => evaluate_hose_row(cdt, cdn),
	leak_check: (frm, cdt, cdn) => evaluate_hose_row(cdt, cdn),
});

// Mirrors crimp_status() in qc_inspection.py.
function hose_crimp_status(r) {
	if (!flt(r.crimp_min) && !flt(r.crimp_max)) return "";
	let measured = 0;
	for (const v of [flt(r.crimp_a), flt(r.crimp_b)]) {
		if (!v) continue;
		if (v < flt(r.crimp_min) || v > flt(r.crimp_max)) return "Out of Spec";
		measured += 1;
	}
	return measured === 2 ? "In Spec" : "";
}

// Mirrors evaluate_hose() in qc_inspection.py; the server result on save is final.
function evaluate_hose_row(cdt, cdn, changed) {
	const r = locals[cdt][cdn];
	const crimp = hose_crimp_status(r);
	let result = "";
	if (crimp === "Out of Spec") {
		result = "Fail";
	} else {
		const crimp_spec = flt(r.crimp_min) || flt(r.crimp_max);
		const complete =
			r.leak_check &&
			flt(r.pressure_reached) &&
			(!crimp_spec || crimp) &&
			(!flt(r.hold_spec_min) || flt(r.hold_actual_min));
		if (complete) {
			let ok =
				r.leak_check === "No Leak" && flt(r.pressure_reached) >= flt(r.test_pressure_spec);
			if (flt(r.hold_spec_min)) ok = ok && flt(r.hold_actual_min) >= flt(r.hold_spec_min);
			result = ok ? "Pass" : "Fail";
		}
	}
	if (r.crimp_status !== crimp) frappe.model.set_value(cdt, cdn, "crimp_status", crimp);
	if (r.result !== result) frappe.model.set_value(cdt, cdn, "result", result);
	const value = changed && flt(r[changed]);
	if (value && (value < flt(r.crimp_min) || value > flt(r.crimp_max))) {
		frappe.msgprint({
			title: __("Crimp out of spec"),
			message: __(
				"Hose {0} {1}: {2} in is outside {3} - {4} in ({5}). The hose fails: enter a finding. A Critical Non Conformance is raised when this inspection is submitted.",
				[
					r.hose_tag,
					changed === "crimp_a" ? __("End A") : __("End B"),
					value,
					flt(r.crimp_min),
					flt(r.crimp_max),
					r.spec_basis || __("PSIF Standard"),
				]
			),
			indicator: "red",
		});
	}
}

frappe.ui.form.on("QC PMG Test", {
	nameplate_verified: (frm, cdt, cdn) => evaluate_pmg_row(cdt, cdn),
	rotation_verified: (frm, cdt, cdn) => evaluate_pmg_row(cdt, cdn),
	relief_as_set: (frm, cdt, cdn) => evaluate_pmg_row(cdt, cdn),
	compensator_as_set: (frm, cdt, cdn) => evaluate_pmg_row(cdt, cdn),
	motor_amps(frm, cdt, cdn) {
		const r = locals[cdt][cdn];
		if (flt(r.motor_fla) && flt(r.motor_amps) > flt(r.motor_fla)) {
			frappe.show_alert(
				{
					message: __("{0}: running amps {1} exceed nameplate FLA {2}.", [
						r.pmg_tag,
						r.motor_amps,
						r.motor_fla,
					]),
					indicator: "orange",
				},
				7
			);
		}
	},
});

// Mirrors evaluate_pmg() in qc_inspection.py; the server result on save is final.
function evaluate_pmg_row(cdt, cdn) {
	const r = locals[cdt][cdn];
	if (r.result === "N/A") return;
	let result = null; // null = leave the inspector's choice
	if (r.nameplate_verified === "No" || r.rotation_verified === "No") {
		result = "Fail";
	} else if (flt(r.tolerance_psi)) {
		const pairs = [
			[flt(r.relief_spec), flt(r.relief_as_set)],
			[flt(r.compensator_spec), flt(r.compensator_as_set)],
		];
		const complete =
			r.nameplate_verified && r.rotation_verified && pairs.every(([s, a]) => !s || a);
		result = complete
			? pairs.every(([s, a]) => !s || Math.abs(a - s) <= flt(r.tolerance_psi))
				? "Pass"
				: "Fail"
			: "";
	}
	if (result !== null && r.result !== result) frappe.model.set_value(cdt, cdn, "result", result);
}
