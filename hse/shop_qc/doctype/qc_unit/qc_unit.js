// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const STAGE_COLORS = {
	Accepted: "green",
	Rejected: "red",
	Pending: "orange",
	Draft: "gray",
	"Not Started": "light-gray",
};

// Load a QC Document Template into a document table. Keeps the reference and attachment
// already entered for any document that is still on the list.
function hse_load_document_template(frm, link, table) {
	const template = frm.doc[link];
	if (!template) return;
	const load = () =>
		frappe
			.xcall("hse.shop_qc.doctype.qc_unit.qc_unit.get_document_template_rows", { template })
			.then((rows) => {
				const kept = {};
				(frm.doc[table] || []).forEach(
					(r) => (kept[(r.document || "").toLowerCase()] = r)
				);
				frm.clear_table(table);
				rows.forEach((row) => {
					const old = kept[row.document.toLowerCase()];
					frm.add_child(table, {
						document: row.document,
						required: (old && old.required) || row.required,
						reference: (old && old.reference) || row.reference,
						attachment: old && old.attachment,
					});
				});
				frm.refresh_field(table);
			});
	if ((frm.doc[table] || []).length) {
		frappe.confirm(
			__(
				"Replace the {0} rows with template {1}? References and attachments already entered are kept.",
				[__(frappe.meta.get_label(frm.doctype, table)), template]
			),
			load
		);
	} else {
		load();
	}
}

// Repair Costing Worksheet: mirrors hse/shop_qc/repair_costing.py (the server recalculates on save).
// Percentages are whole numbers (5 = 5 %); the line Multiplier is a fraction (0.5 = 50 %).
const REPAIR_PRICING_INPUTS = [
	"parts_burden_pct",
	"parts_freight_pct",
	"parts_expendables_pct",
	"parts_margin_pct",
	"accessories_burden_pct",
	"accessories_freight_pct",
	"accessories_expendables_pct",
	"accessories_margin_pct",
	"labor_inspection_hr",
	"labor_repair_hr",
	"labor_assembly_hr",
	"labor_testing_hr",
	"labor_cost_rate",
	"labor_sell_rate",
	"new_unit_price",
	"new_unit_accessories_price",
];

function hse_repair_group(doc, prefix, rows) {
	let total = 0;
	for (const r of rows || []) {
		r.cost_each = flt(r.list_price) * flt(r.multiplier);
		r.extended_cost = flt(r.qty) * flt(r.cost_each);
		total += r.extended_cost;
	}
	doc[`${prefix}_total`] = total;
	let cost = total;
	for (const part of ["burden", "freight", "expendables"]) {
		const amount = (total * flt(doc[`${prefix}_${part}_pct`])) / 100;
		doc[`${prefix}_${part}`] = amount;
		cost += amount;
	}
	doc[`${prefix}_cost_total`] = cost;
	const margin = flt(doc[`${prefix}_margin_pct`]) / 100;
	const sell = cost && margin < 1 ? cost / (1 - margin) : 0;
	doc[`${prefix}_sell_price`] = sell;
	doc[`${prefix}_margin`] = sell ? sell - cost : 0;
}

function hse_calc_repair_costing(frm) {
	const doc = frm.doc;
	if (doc.job_type !== "Repair") return;
	hse_repair_group(doc, "parts", doc.repair_parts);
	hse_repair_group(doc, "accessories", doc.accessory_items);
	const insp = flt(doc.labor_inspection_hr);
	const rep = flt(doc.labor_repair_hr);
	const assy = flt(doc.labor_assembly_hr);
	const test = flt(doc.labor_testing_hr);
	const hours = insp + rep + assy + test;
	doc.labor_total_hr = hours;
	doc.labor_inspection_cost_hr = insp;
	doc.labor_rep_assy_hr = rep + assy;
	doc.labor_testing_cost_hr = test;
	doc.labor_cost = hours * flt(doc.labor_cost_rate);
	doc.labor_sell_price = hours * flt(doc.labor_sell_rate);
	doc.repair_price = flt(doc.parts_sell_price) + flt(doc.labor_sell_price);
	doc.repair_accessories_price = doc.repair_price + flt(doc.accessories_sell_price);
	doc.repair_pct_of_new = flt(doc.new_unit_price)
		? (doc.repair_price / flt(doc.new_unit_price)) * 100
		: 0;
	doc.repair_accessories_pct_of_new = flt(doc.new_unit_accessories_price)
		? (doc.repair_accessories_price / flt(doc.new_unit_accessories_price)) * 100
		: 0;
	frm.refresh_fields();
}

frappe.ui.form.on("QC Unit", {
	construction_document_template(frm) {
		hse_load_document_template(
			frm,
			"construction_document_template",
			"construction_documents"
		);
	},

	quality_document_template(frm) {
		hse_load_document_template(frm, "quality_document_template", "quality_documents");
	},

	setup(frm) {
		for (const [link, category] of [
			["construction_document_template", "Construction"],
			["quality_document_template", "Quality"],
		]) {
			frm.set_query(link, () => ({ filters: { category, disabled: 0 } }));
		}
		frm.set_query("failure_cause", () => ({ filters: { disabled: 0 } }));
		frm.set_query("shop", () => ({ filters: { disabled: 0 } }));
	},

	job_type(frm) {
		if (frm.doc.job_type === "Repair" && !frm.doc.received_date) {
			frm.set_value("received_date", frappe.datetime.get_today());
		}
		hse_calc_repair_costing(frm);
	},

	shop(frm) {
		if (!frm.doc.shop) return;
		frappe.db.get_value("Build Shop", frm.doc.shop, "is_repair_shop").then((r) => {
			if (!cint(r.message && r.message.is_repair_shop)) return;
			frm.set_value("job_type", "Repair");
			if (frm.is_new() && frm.doc.product_type === "Power Unit") {
				// Repairs are normally worked at component level; change it back for a whole-unit repair.
				frm.set_value("product_type", "Component");
			}
		});
	},

	repair_parts_remove: hse_calc_repair_costing,
	accessory_items_remove: hse_calc_repair_costing,

	refresh(frm) {
		if (frm.doc.trulinx_url) {
			frm.add_web_link(frm.doc.trulinx_url, __("Open in TrulinX"));
		}
		if (frm.doc.qc_flag) {
			frm.dashboard.set_headline_alert(frm.doc.qc_flag, "red");
		} else if (frm.doc.status === "QC Hold") {
			frm.dashboard.set_headline_alert(
				__("QC Hold: {0} open Non Conformance(s). Do not ship.", [
					frm.doc.open_non_conformances,
				]),
				"red"
			);
		}
		if (frm.doc.sync_source === "TrulinX") {
			frm.set_intro(
				__(
					"TrulinX fields on this record are overwritten by the next sync. QC fields are not."
				),
				"blue"
			);
		}
		if (!frm.is_new() && !["Shipped", "Cancelled"].includes(frm.doc.status)) {
			frm.add_custom_button(
				__("QC Inspection"),
				() => {
					frappe.new_doc("QC Inspection", { qc_unit: frm.doc.name });
				},
				__("Create")
			);
		}
		if (!frm.is_new()) frm.trigger("hose_build");
		if (!frm.is_new()) frm.trigger("sub_assemblies");
		frm.trigger("required_qc");
		if (!frm.is_new()) {
			frm.add_custom_button(
				frm.doc.job_type === "Repair" ? __("Repair Report") : __("QC Certificate"),
				() => {
					frappe
						.xcall("hse.shop_qc.utils.get_certificate_format", {
							qc_unit: frm.doc.name,
						})
						.then((format) =>
							frappe.set_route("print", "QC Unit", frm.doc.name, { format })
						);
				},
				__("View")
			);
			if (frm.doc.job_type === "Repair") {
				frm.add_custom_button(
					__("Repair Evaluation Report"),
					() =>
						frappe.set_route("print", "QC Unit", frm.doc.name, {
							format: "Repair Evaluation Report",
						}),
					__("View")
				);
			}
			frm.trigger("render_stage_progress");
			if (cint(frm.doc.unit_qty) > 1) frm.trigger("order_units");
		}
	},

	// Required QC: the stages this unit needs, with a draft inspection for each.
	required_qc(frm) {
		const grid = frm.fields_dict.qc_stages && frm.fields_dict.qc_stages.grid;
		if (!grid) return;
		if (!grid.qc_load_button) {
			grid.qc_load_button = grid.add_custom_button(__("Load QC Stages"), () =>
				frm.trigger("load_qc_stages")
			);
		}
		grid.qc_load_button.toggle(
			!frm.is_new() && !(frm.doc.qc_stages || []).length && !!frm.doc.shop
		);
		if (
			!frm.is_new() &&
			(frm.doc.qc_stages || []).length &&
			!["Shipped", "Cancelled"].includes(frm.doc.status)
		) {
			frm.add_custom_button(
				__("Draft Inspections"),
				() => {
					if (frm.is_dirty()) {
						frappe.msgprint(__("Save the unit first."));
						return;
					}
					frappe
						.xcall("hse.shop_qc.unit_stages.make_draft_inspections", {
							qc_unit: frm.doc.name,
						})
						.then(() => frm.reload_doc());
				},
				__("Create")
			);
		}
	},

	load_qc_stages(frm) {
		frappe
			.xcall("hse.shop_qc.unit_stages.get_qc_stage_rows", {
				shop: frm.doc.shop,
				job_type: frm.doc.job_type,
			})
			.then((rows) => {
				frm.clear_table("qc_stages");
				rows.forEach((r) => frm.add_child("qc_stages", r));
				frm.refresh_field("qc_stages");
				frm.trigger("required_qc");
				frappe.show_alert({
					message: __(
						"Untick any stage this unit does not need, save, then use Create > Draft Inspections."
					),
					indicator: "blue",
				});
			});
	},

	// Sub-assemblies on their own work order (e.g. a control panel), tested with this unit.
	sub_assemblies(frm) {
		const link = (name) =>
			`<a href="/app/qc-unit/${encodeURIComponent(name)}">${frappe.utils.escape_html(
				name
			)}</a>`;
		if (frm.doc.installed_in) {
			frm.dashboard.add_comment(
				__("Installed in QC Unit {0}: tested and released with that unit", [
					link(frm.doc.installed_in),
				]),
				"blue",
				true
			);
			return;
		}
		if (frm.doc.job_type === "Repair" || frm.doc.parent_qc_unit) return;
		frappe
			.xcall("hse.shop_qc.sub_assemblies.get_sub_assembly_info", { qc_unit: frm.doc.name })
			.then((r) => {
				(r.sub_units || []).forEach((u) => {
					const wo = u.trulinx_work_order
						? ` WO ${frappe.utils.escape_html(u.trulinx_work_order)}`
						: "";
					const sn = u.serial_no ? `, S/N ${frappe.utils.escape_html(u.serial_no)}` : "";
					frm.dashboard.add_comment(
						__("Sub-assembly {0}{1}{2}: {3}", [link(u.name), wo, sn, __(u.status)]),
						"blue",
						true
					);
				});
				if ((r.blockers || []).length) {
					frm.dashboard.add_comment(
						__("Testing and final release wait for: {0}", [
							r.blockers.map((b) => frappe.utils.escape_html(b)).join("; "),
						]),
						"red",
						true
					);
				}
				if (frm.doc.status === "Cancelled") return;
				frm.add_custom_button(
					__("Link Sub-Assembly"),
					() => {
						const d = new frappe.ui.Dialog({
							title: __("Link Sub-Assembly"),
							fields: [
								{
									fieldname: "sub_unit",
									fieldtype: "Link",
									options: "QC Unit",
									label: __("QC Unit (e.g. control panel work order)"),
									reqd: 1,
									get_query: () => ({
										filters: {
											name: ["!=", frm.doc.name],
											job_type: ["!=", "Repair"],
											status: ["!=", "Cancelled"],
										},
									}),
								},
							],
							primary_action_label: __("Link"),
							primary_action: (v) =>
								frappe
									.xcall("hse.shop_qc.sub_assemblies.link_sub_assembly", {
										qc_unit: frm.doc.name,
										sub_unit: v.sub_unit,
									})
									.then(() => {
										d.hide();
										frm.reload_doc();
									}),
						});
						d.show();
					},
					__("Create")
				);
			});
	},

	// Hose build: a Hose Assembly QC Unit on this unit's work order (<unit>-H).
	hose_build(frm) {
		const link = (name) =>
			`<a href="/app/qc-unit/${encodeURIComponent(name)}">${frappe.utils.escape_html(
				name
			)}</a>`;
		if (frm.doc.parent_qc_unit) {
			frm.dashboard.add_comment(
				__("Hose build for QC Unit {0}", [link(frm.doc.parent_qc_unit)]),
				"blue",
				true
			);
			return;
		}
		if (frm.doc.job_type === "Repair" || frm.doc.product_type === "Hose Assembly") return;
		frappe
			.xcall("hse.shop_qc.multi_unit.get_related_hose_build", { qc_unit: frm.doc.name })
			.then((r) => {
				if (r.hose_build) {
					frm.dashboard.add_comment(
						__("Hose build: {0}", [link(r.hose_build)]),
						"blue",
						true
					);
				}
				if (!r.hose_build && frm.doc.status === "Cancelled") return;
				frm.add_custom_button(
					__("Hose Build"),
					() => {
						if (r.hose_build) return frappe.set_route("Form", "QC Unit", r.hose_build);
						frappe.confirm(
							__(
								"Create a hose build on work order {0}? It is a Hose Assembly QC Unit in the Hose shop named {1}-H, with this unit's customer, order and dates.",
								[frm.doc.trulinx_work_order || "", frm.doc.name]
							),
							() =>
								frappe
									.xcall("hse.shop_qc.multi_unit.create_hose_build", {
										qc_unit: frm.doc.name,
									})
									.then((name) => frappe.set_route("Form", "QC Unit", name))
						);
					},
					__("Create")
				);
			});
	},

	// Orders of more than one unit: one QC Unit per unit (12345-1, 12345-2 ...).
	order_units(frm) {
		frappe
			.xcall("hse.shop_qc.multi_unit.get_order_status", { qc_unit: frm.doc.name })
			.then((r) => {
				const others = (r.units || []).filter((u) => u.name !== frm.doc.name);
				if (others.length) {
					const links = others
						.map(
							(u) =>
								`<a href="/app/qc-unit/${encodeURIComponent(
									u.name
								)}">${frappe.utils.escape_html(
									u.name
								)}</a> (${frappe.utils.escape_html(__(u.status || ""))})`
						)
						.join(", ");
					frm.dashboard.add_comment(
						__("Other units of this order: {0}", [links]),
						"blue",
						true
					);
				}
				if (!r.missing || frm.doc.status === "Cancelled") return;
				frm.add_custom_button(
					__("Create Remaining Units"),
					() =>
						frappe.confirm(
							__(
								"Create the {0} unit(s) not yet entered for this order of {1}? Order data, specs, pump/motor groups, hoses, circuit items and requirements are copied from this unit. Serial No, inspections, NCRs, repair findings and release are not.",
								[r.missing, r.qty]
							),
							() =>
								frappe
									.xcall("hse.shop_qc.multi_unit.create_remaining_units", {
										qc_unit: frm.doc.name,
									})
									.then((res) => {
										frappe.msgprint(
											__("Created: {0}", [(res.created || []).join(", ")]),
											__("Units Created")
										);
										if (res.renamed_to && res.renamed_to !== frm.doc.name) {
											frappe.set_route("Form", "QC Unit", res.renamed_to);
										} else {
											frm.reload_doc();
										}
									})
						),
					__("Create")
				);
			});
	},

	render_stage_progress(frm) {
		const wrapper = frm.get_field("stage_progress").$wrapper;
		frappe.call({
			method: "hse.shop_qc.utils.get_stage_progress",
			args: { qc_unit: frm.doc.name },
			callback: (r) => {
				const rows = (r.message || [])
					.map((s) => {
						const color = STAGE_COLORS[s.status] || "gray";
						const link = s.inspection
							? `<a href="/app/qc-inspection/${encodeURIComponent(
									s.inspection
							  )}">${frappe.utils.escape_html(s.inspection)}</a>`
							: "";
						return `<tr>
						<td>${s.sequence}</td>
						<td>${frappe.utils.escape_html(s.stage)}${
							s.is_final_release
								? ` <span class="text-muted">(${__("release")})</span>`
								: ""
						}${
							s.is_required
								? ""
								: ` <span class="text-muted">(${__("optional")})</span>`
						}</td>
						<td><span class="indicator-pill ${color}">${__(s.status)}</span></td>
						<td>${link}</td>
						<td>${s.inspection_date ? frappe.datetime.str_to_user(s.inspection_date) : ""}</td>
						<td>${frappe.utils.escape_html(s.inspector_name || "")}</td>
					</tr>`;
					})
					.join("");
				wrapper.html(`<table class="table table-bordered table-sm" style="margin-bottom:0">
					<thead><tr><th>#</th><th>${__("Stage")}</th><th>${__("Status")}</th><th>${__(
					"Inspection"
				)}</th><th>${__("Date")}</th><th>${__("Inspector")}</th></tr></thead>
					<tbody>${rows}</tbody></table>`);
			},
		});
	},
});

// Hose rows: End B defaults to End A, and crimp values come from the Hose Crimp Spec chart.
// The server repeats both on save (apply_crimp_chart in qc_unit.py).
frappe.ui.form.on("QC Hose Assembly", {
	fitting_a(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.fitting_a && !row.fitting_b) {
			frappe.model.set_value(cdt, cdn, "fitting_b", row.fitting_a);
		}
		fill_crimp_from_chart(cdt, cdn);
	},
	hose_type: (frm, cdt, cdn) => fill_crimp_from_chart(cdt, cdn),
	hose_size: (frm, cdt, cdn) => fill_crimp_from_chart(cdt, cdn),
});

function fill_crimp_from_chart(cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.hose_type || !row.hose_size || !row.fitting_a) return;
	frappe
		.xcall("hse.shop_qc.doctype.hose_crimp_spec.hose_crimp_spec.get_crimp_spec", {
			hose_type: row.hose_type,
			dash_size: row.hose_size,
			fitting: row.fitting_a,
		})
		.then((spec) => {
			if (!spec) {
				frappe.show_alert({
					message: __("No crimp chart entry for {0} {1} {2}. Enter the crimp values.", [
						row.hose_type,
						row.hose_size,
						row.fitting_a,
					]),
					indicator: "orange",
				});
				return;
			}
			frappe.model.set_value(cdt, cdn, {
				crimp_spec: spec.name,
				crimp_diameter_spec: spec.crimp_diameter,
				crimp_tolerance: spec.crimp_tolerance,
				die_size: spec.die_size,
				crimp_spec_source: [
					spec.source,
					spec.revision,
					spec.matched_series ? __("{0} series", [spec.matched_series]) : "",
				]
					.join(" / ")
					.replace(/^( \/ )+|( \/ )+$/g, "")
					.replace(/( \/ )+/g, " / "),
			});
		});
}

// Live costing: line cost each / extended, and the pricing information totals.
frappe.ui.form.on("QC Repair Part", {
	qty: (frm) => hse_calc_repair_costing(frm),
	list_price: (frm) => hse_calc_repair_costing(frm),
	multiplier: (frm) => hse_calc_repair_costing(frm),
});

frappe.ui.form.on(
	"QC Unit",
	Object.fromEntries(REPAIR_PRICING_INPUTS.map((f) => [f, hse_calc_repair_costing]))
);
