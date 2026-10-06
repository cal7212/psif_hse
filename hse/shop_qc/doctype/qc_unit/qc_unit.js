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
	},

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
			frm.trigger("render_stage_progress");
		}
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
