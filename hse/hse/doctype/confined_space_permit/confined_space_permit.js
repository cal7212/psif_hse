// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

// Mirrors judge_reading() in confined_space_permit.py; the server judges every test on save.
function csp_judge(frm, t) {
	if ([null, undefined, ""].includes(t.oxygen_pct) || [null, undefined, ""].includes(t.lel_pct))
		return "";
	const d = frm.doc;
	const bad =
		flt(t.oxygen_pct) < flt(d.oxygen_min) ||
		flt(t.oxygen_pct) > flt(d.oxygen_max) ||
		flt(t.lel_pct) > flt(d.lel_max) ||
		(flt(d.h2s_max) && flt(t.h2s_ppm) > flt(d.h2s_max)) ||
		(flt(d.co_max) && flt(t.co_ppm) > flt(d.co_max));
	return bad ? "Not Acceptable" : "Acceptable";
}

function csp_test_changed(frm, cdt, cdn) {
	const t = locals[cdt][cdn];
	const result = csp_judge(frm, t);
	frappe.model.set_value(cdt, cdn, "result", result);
	if (result === "Not Acceptable") {
		frappe.msgprint({
			title: __("Prohibited Condition"),
			message: __(
				"This reading is outside the acceptable entry conditions. No entry; entrants already inside must leave now."
			),
			indicator: "red",
		});
	}
}

frappe.ui.form.on("Confined Space Permit", {
	setup(frm) {
		frm.set_query("entry_supervisor", () => ({ filters: { status: "Active" } }));
		frm.set_query("employee", "workers", () => ({ filters: { status: "Active" } }));
		frm.set_query("job_hazard_analysis", () => ({ filters: { status: "Active" } }));
	},
	refresh(frm) {
		window.hse.permits.refresh(frm, "Issued", "permit_end");
		const df = frappe.meta.get_docfield(
			"Confined Space Atmospheric Test",
			"result",
			frm.doc.name
		);
		if (df) {
			df.formatter = (value) =>
				value
					? `<span class="indicator-pill ${
							value === "Acceptable" ? "green" : "red"
					  }">${__(value)}</span>`
					: "";
		}
	},
});

frappe.ui.form.on("Confined Space Atmospheric Test", {
	oxygen_pct: csp_test_changed,
	lel_pct: csp_test_changed,
	h2s_ppm: csp_test_changed,
	co_ppm: csp_test_changed,
	atmospheric_tests_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if ((frm.doc.atmospheric_tests || []).length === 1) row.test_type = "Pre-Entry";
	},
});
