// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

// Mirrors risk_assessment.py; the server recalculates on save.
const RA_METHOD = "hse.hse.doctype.risk_assessment.risk_assessment";
const RATING_BANDS = [
	[20, "Critical"],
	[10, "High"],
	[5, "Medium"],
	[1, "Low"],
];
const RATING_COLORS = {
	Low: { bg: "#d9f2d9", fg: "#1e6b1e", indicator: "green" },
	Medium: { bg: "#fff3c4", fg: "#7a5b00", indicator: "yellow" },
	High: { bg: "#ffd8b0", fg: "#8a3c00", indicator: "orange" },
	Critical: { bg: "#f8c4c4", fg: "#8b0000", indicator: "red" },
};
const SEVERITY_LABELS = ["Negligible", "Minor", "Moderate", "Major", "Catastrophic"];
const LIKELIHOOD_LABELS = ["Rare", "Unlikely", "Possible", "Likely", "Almost Certain"];

function ra_level(value) {
	const n = cint(
		String(value || "")
			.trim()
			.split(" ")[0]
	);
	return n >= 1 && n <= 5 ? n : 0;
}

function ra_score(severity, likelihood) {
	const s = ra_level(severity);
	const l = ra_level(likelihood);
	return s && l ? s * l : 0;
}

function ra_rating(score) {
	for (const [threshold, rating] of RATING_BANDS) {
		if (cint(score) >= threshold) return rating;
	}
	return "";
}

function rating_badge(rating, score) {
	const c = RATING_COLORS[rating];
	if (!c) return "";
	const text = score ? `${score} ${__(rating)}` : __(rating);
	return `<span style="background:${c.bg};color:${c.fg};padding:1px 6px;border-radius:4px;font-weight:600">${text}</span>`;
}

function score_row(cdt, cdn) {
	const row = locals[cdt][cdn];
	const no_controls = !String(row.additional_controls || "").trim();
	if (no_controls) {
		row.residual_severity = row.initial_severity;
		row.residual_likelihood = row.initial_likelihood;
	}
	const initial = ra_score(row.initial_severity, row.initial_likelihood);
	const residual = ra_score(row.residual_severity, row.residual_likelihood);
	frappe.model.set_value(cdt, cdn, {
		residual_severity: row.residual_severity,
		residual_likelihood: row.residual_likelihood,
		initial_score: initial,
		initial_rating: ra_rating(initial),
		residual_score: residual,
		residual_rating: ra_rating(residual),
	});
	if (initial && residual > initial) {
		frappe.show_alert({
			message: __("Hazard row {0}: the residual risk is higher than the initial risk.", [
				row.idx,
			]),
			indicator: "orange",
		});
	}
}

function render_matrix(frm) {
	const field = frm.get_field("risk_matrix");
	if (!field) return;
	let head = `<th style="padding:4px 6px"></th>`;
	SEVERITY_LABELS.forEach((label, i) => {
		head += `<th style="padding:4px 6px;text-align:center;font-weight:600">${
			i + 1
		}<br><span class="text-muted small">${__(label)}</span></th>`;
	});
	let body = "";
	for (let l = 5; l >= 1; l--) {
		let cells = `<th style="padding:4px 6px;text-align:right;font-weight:600">${l} <span class="text-muted small">${__(
			LIKELIHOOD_LABELS[l - 1]
		)}</span></th>`;
		for (let s = 1; s <= 5; s++) {
			const c = RATING_COLORS[ra_rating(s * l)];
			cells += `<td style="background:${c.bg};color:${
				c.fg
			};text-align:center;padding:6px;min-width:48px;font-weight:600">${s * l}</td>`;
		}
		body += `<tr>${cells}</tr>`;
	}
	field.$wrapper.html(`
		<details>
			<summary class="text-muted" style="cursor:pointer">${__(
				"Risk matrix: severity × likelihood"
			)}</summary>
			<div style="overflow-x:auto;margin-top:8px">
				<table style="border-collapse:separate;border-spacing:2px">
					<thead><tr>${head}</tr></thead>
					<tbody>${body}</tbody>
				</table>
				<p class="text-muted small" style="margin-top:6px">
					${__(
						"Low 1–4: manage by routine procedures. Medium 5–9: reduce where reasonably practicable. High 10–16: reduce before work starts; approving with High remaining needs a written acceptance. Critical 20–25: the work must not go ahead."
					)}
				</p>
			</div>
		</details>`);
}

function set_rating_formatters(frm) {
	["initial_rating", "residual_rating"].forEach((fieldname) => {
		const df = frappe.meta.get_docfield("Risk Assessment Hazard", fieldname, frm.doc.name);
		if (df) {
			df.formatter = (value, _df, _opts, doc) =>
				rating_badge(value, doc && doc[fieldname.replace("_rating", "_score")]);
		}
	});
}

function set_next_review(frm) {
	if (frm.doc.docstatus !== 0) return;
	const months = cint(frm.doc.review_interval_months);
	if (frm.doc.assessment_date && months) {
		frm.set_value(
			"next_review_date",
			frappe.datetime.add_months(frm.doc.assessment_date, months)
		);
	}
}

frappe.ui.form.on("Risk Assessment", {
	setup(frm) {
		frm.set_query("assessed_by", () => ({ filters: { status: "Active" } }));
		frm.set_query("employee", "team", () => ({ filters: { status: "Active" } }));
		frm.set_query("injury_report", () => ({ filters: { docstatus: ["!=", 2] } }));
		frm.set_query("asset", () => ({ filters: { docstatus: 1 } }));
	},

	refresh(frm) {
		render_matrix(frm);
		set_rating_formatters(frm);
		frm.trigger("set_intro");

		if (frm.doc.docstatus === 1 && frm.doc.status === "Active") {
			frm.add_custom_button(__("Start Review"), () => {
				frappe.model.open_mapped_doc({ method: `${RA_METHOD}.make_review`, frm });
			});
		}
		["previous_assessment", "superseded_by"].forEach((fieldname) => {
			if (frm.doc[fieldname]) {
				frm.add_custom_button(
					fieldname === "superseded_by"
						? __("Current Revision")
						: __("Previous Revision"),
					() => frappe.set_route("Form", "Risk Assessment", frm.doc[fieldname]),
					__("View")
				);
			}
		});
		if (frm.doc.injury_report) {
			frm.add_custom_button(
				__("Incident Report"),
				() => frappe.set_route("Form", "Injury_Illness Report", frm.doc.injury_report),
				__("View")
			);
		}
	},

	set_intro(frm) {
		const today = frappe.datetime.get_today();
		if (frm.doc.status === "Superseded") {
			frm.set_intro(
				__("Superseded by {0}. Work to the current revision.", [frm.doc.superseded_by]),
				"orange"
			);
		} else if (
			frm.doc.status === "Active" &&
			frm.doc.next_review_date &&
			frm.doc.next_review_date <= today
		) {
			frm.set_intro(
				__("Review due since {0}. Use Start Review to make the next revision.", [
					frappe.datetime.str_to_user(frm.doc.next_review_date),
				]),
				"orange"
			);
		} else if (frm.doc.docstatus === 0 && frm.doc.previous_assessment) {
			frm.set_intro(
				__("Revision {0}. When approved, {1} becomes Superseded.", [
					frm.doc.revision,
					frm.doc.previous_assessment,
				]),
				"blue"
			);
		}
	},

	assessment_date: set_next_review,
	review_interval_months: set_next_review,

	hazards_remove(frm) {
		frm.refresh_field("hazards");
	},
});

frappe.ui.form.on("Risk Assessment Hazard", {
	initial_severity: (frm, cdt, cdn) => score_row(cdt, cdn),
	initial_likelihood: (frm, cdt, cdn) => score_row(cdt, cdn),
	residual_severity: (frm, cdt, cdn) => score_row(cdt, cdn),
	residual_likelihood: (frm, cdt, cdn) => score_row(cdt, cdn),
	additional_controls: (frm, cdt, cdn) => score_row(cdt, cdn),
});
