// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

// Mirrors risk_rating() / risk_score() in risk_assessment.py; the server recalculates on save.
const JHA_METHOD = "hse.hse.doctype.job_hazard_analysis.job_hazard_analysis";
const JHA_BANDS = [
	[20, "Critical"],
	[10, "High"],
	[5, "Medium"],
	[1, "Low"],
];
const JHA_COLORS = {
	Low: ["#d9f2d9", "#1e6b1e"],
	Medium: ["#fff3c4", "#7a5b00"],
	High: ["#ffd8b0", "#8a3c00"],
	Critical: ["#f8c4c4", "#8b0000"],
};

function jha_level(value) {
	const n = cint(
		String(value || "")
			.trim()
			.split(" ")[0]
	);
	return n >= 1 && n <= 5 ? n : 0;
}

function jha_score_step(cdt, cdn) {
	const row = locals[cdt][cdn];
	const s = jha_level(row.severity);
	const l = jha_level(row.likelihood);
	const score = s && l ? s * l : 0;
	const band = JHA_BANDS.find(([threshold]) => score >= threshold);
	frappe.model.set_value(cdt, cdn, { risk_score: score, risk_rating: band ? band[1] : "" });
}

frappe.ui.form.on("Job Hazard Analysis", {
	setup(frm) {
		["prepared_by", "supervisor"].forEach((f) =>
			frm.set_query(f, () => ({ filters: { status: "Active" } }))
		);
		frm.set_query("risk_assessment", () => ({ filters: { status: "Active" } }));
		frm.set_query("employee", "workers", () => ({ filters: { status: "Active" } }));
	},

	refresh(frm) {
		const df = frappe.meta.get_docfield(
			"Job Hazard Analysis Step",
			"risk_rating",
			frm.doc.name
		);
		if (df) {
			df.formatter = (value, _df, _opts, doc) => {
				const c = JHA_COLORS[value];
				return c
					? `<span style="background:${c[0]};color:${
							c[1]
					  };padding:1px 6px;border-radius:4px;font-weight:600">${
							doc && doc.risk_score ? doc.risk_score + " " : ""
					  }${__(value)}</span>`
					: "";
			};
		}
		if (frm.doc.docstatus === 1 && frm.doc.status === "Active") {
			frm.add_custom_button(__("Start Review"), () =>
				frappe.model.open_mapped_doc({ method: `${JHA_METHOD}.make_review`, frm })
			);
			const permits = [
				["req_confined_space", "Confined Space Permit", "confined_space_permit"],
				[
					"req_energized_electrical",
					"Energized Electrical Work Permit",
					"energized_electrical_work_permit",
				],
			];
			permits.forEach(([flag, doctype, module]) => {
				if (!frm.doc[flag]) return;
				frm.add_custom_button(
					__(doctype),
					() =>
						frappe.model.open_mapped_doc({
							method: `hse.hse.doctype.${module}.${module}.make_from_jha`,
							frm,
						}),
					__("Create")
				);
			});
		}
		if (frm.doc.superseded_by) {
			frm.set_intro(
				__("Superseded by {0}. Work to the current revision.", [frm.doc.superseded_by]),
				"orange"
			);
		} else if (
			frm.doc.status === "Active" &&
			frm.doc.next_review_date &&
			frm.doc.next_review_date <= frappe.datetime.get_today()
		) {
			frm.set_intro(__("Review due. Use Start Review to make the next revision."), "orange");
		} else if (frm.doc.docstatus === 0 && frm.doc.previous_analysis) {
			frm.set_intro(
				__("Revision {0}. When approved, {1} becomes Superseded.", [
					frm.doc.revision,
					frm.doc.previous_analysis,
				]),
				"blue"
			);
		}
	},

	analysis_date: (frm) => frm.trigger("set_next_review"),
	review_interval_months: (frm) => frm.trigger("set_next_review"),
	set_next_review(frm) {
		const months = cint(frm.doc.review_interval_months);
		if (frm.doc.docstatus === 0 && frm.doc.analysis_date && months) {
			frm.set_value(
				"next_review_date",
				frappe.datetime.add_months(frm.doc.analysis_date, months)
			);
		}
	},
});

frappe.ui.form.on("Job Hazard Analysis Step", {
	severity: (frm, cdt, cdn) => jha_score_step(cdt, cdn),
	likelihood: (frm, cdt, cdn) => jha_score_step(cdt, cdn),
});
