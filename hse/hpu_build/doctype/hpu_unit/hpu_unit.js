// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const STAGE_COLORS = { Accepted: "green", Rejected: "red", Pending: "orange", Draft: "gray", "Not Started": "light-gray" };

frappe.ui.form.on("HPU Unit", {
	refresh(frm) {
		if (frm.doc.trulinx_url) {
			frm.add_web_link(frm.doc.trulinx_url, __("Open in TrulinX"));
		}
		if (frm.doc.qc_flag) {
			frm.dashboard.set_headline_alert(frm.doc.qc_flag, "red");
		} else if (frm.doc.status === "QC Hold") {
			frm.dashboard.set_headline_alert(
				__("QC Hold: {0} open Non Conformance(s). Do not ship.", [frm.doc.open_non_conformances]), "red");
		}
		if (frm.doc.sync_source === "TrulinX") {
			frm.set_intro(__("TrulinX fields on this record are overwritten by the next sync. QC fields are not."), "blue");
		}
		if (!frm.is_new() && !["Shipped", "Cancelled"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Build Inspection"), () => {
				frappe.new_doc("HPU Build Inspection", { hpu_unit: frm.doc.name });
			}, __("Create"));
		}
		if (!frm.is_new()) {
			frm.add_custom_button(__("QC Certificate"), () => {
				frappe.set_route("print", "HPU Unit", frm.doc.name, { format: "HPU QC Certificate" });
			}, __("View"));
			frm.trigger("render_stage_progress");
		}
	},

	render_stage_progress(frm) {
		const wrapper = frm.get_field("stage_progress").$wrapper;
		frappe.call({
			method: "hse.hpu_build.utils.get_stage_progress",
			args: { hpu_unit: frm.doc.name },
			callback: (r) => {
				const rows = (r.message || []).map((s) => {
					const color = STAGE_COLORS[s.status] || "gray";
					const link = s.inspection
						? `<a href="/app/hpu-build-inspection/${encodeURIComponent(s.inspection)}">${frappe.utils.escape_html(s.inspection)}</a>`
						: "";
					return `<tr>
						<td>${s.sequence}</td>
						<td>${frappe.utils.escape_html(s.stage)}${s.is_final_release ? ` <span class="text-muted">(${__("release")})</span>` : ""}${s.is_required ? "" : ` <span class="text-muted">(${__("optional")})</span>`}</td>
						<td><span class="indicator-pill ${color}">${__(s.status)}</span></td>
						<td>${link}</td>
						<td>${s.inspection_date ? frappe.datetime.str_to_user(s.inspection_date) : ""}</td>
						<td>${frappe.utils.escape_html(s.inspector_name || "")}</td>
					</tr>`;
				}).join("");
				wrapper.html(`<table class="table table-bordered table-sm" style="margin-bottom:0">
					<thead><tr><th>#</th><th>${__("Stage")}</th><th>${__("Status")}</th><th>${__("Inspection")}</th><th>${__("Date")}</th><th>${__("Inspector")}</th></tr></thead>
					<tbody>${rows}</tbody></table>`);
			},
		});
	},
});
