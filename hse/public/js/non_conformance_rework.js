// QM-104 Rev. 3 Rework on Nonconformance Report (loaded alongside non_conformance.js)
const HSE_NCR_CRITERIA = [
	["crit_scrap", __("Results in scrap of a finished part")],
	[
		"crit_cannot_rework",
		__(
			"Can't be reworked to the drawing or spec (needs use-as-is, repair or deviation per QM-144, or Engineering or customer approval)"
		),
	],
	[
		"crit_customer_safety",
		__("Affects a customer requirement, safety or the promised ship date"),
	],
	[
		"crit_supplier",
		__("Supplier caused or contributed, or suspected counterfeit (QM-134 / QM-310)"),
	],
];

// NCR Criteria Evaluation on the Rework tab: rw_<criterion>, answered No or Yes.
const HSE_RW_EVAL = HSE_NCR_CRITERIA.map(([f]) => "rw_" + f);

const hse_eval_handlers = {};
for (const ev of HSE_RW_EVAL) {
	hse_eval_handlers[ev] = (frm) => hse_eval_changed(frm, ev);
}

frappe.ui.form.on("Nonconformance Report", {
	...hse_eval_handlers,
	onload(frm) {
		hse_rework_print_format(frm);
	},
	record_type(frm) {
		hse_rework_print_format(frm);
	},
	refresh(frm) {
		hse_rework_print_format(frm);
		if (frm.is_new()) return;
		const rework = frm.doc.record_type === "Rework";

		if (rework) {
			frm.add_custom_button(
				__("Rework Report"),
				() => hse_open_print(frm, "QM-104 Rework Report"),
				__("View")
			);
		}
		if (frm.doc.escalated_to) {
			frm.add_custom_button(
				__("NCR {0}", [frm.doc.escalated_to]),
				() => frappe.set_route("Form", "Nonconformance Report", frm.doc.escalated_to),
				__("View")
			);
			frm.dashboard.set_headline_alert(
				__("This Rework was escalated to NCR {0}.", [frm.doc.escalated_to]),
				"blue"
			);
		} else if (frm.doc.escalated_from) {
			frm.add_custom_button(
				__("Rework {0}", [frm.doc.escalated_from]),
				() => frappe.set_route("Form", "Nonconformance Report", frm.doc.escalated_from),
				__("View")
			);
		}

		if (rework && frm.doc.status === "Open" && frm.perm[0] && frm.perm[0].write) {
			frm.add_custom_button(
				__("Escalate to NCR"),
				() => hse_escalate_dialog(frm),
				__("Create")
			);
		}
		if (rework && frm.doc.status === "Open" && !frm.doc.escalated_to) {
			const open = HSE_RW_EVAL.filter((f) => !["Yes", "No"].includes(frm.doc[f]));
			if (open.length) {
				frm.dashboard.set_headline_alert(
					__(
						"Complete the NCR Criteria Evaluation on the Rework tab ({0} of 4 answered). Any Yes needs an NCR; all No is needed to accept and resolve the Rework.",
						[4 - open.length]
					),
					"orange"
				);
			}
		}
	},
});

function hse_rework_print_format(frm) {
	frm.meta.default_print_format =
		frm.doc.record_type === "Rework"
			? "QM-104 Rework Report"
			: "QM-104 Non-Conformance Report";
}

function hse_open_print(frm, format) {
	const url =
		"/printview?doctype=" +
		encodeURIComponent(frm.doctype) +
		"&name=" +
		encodeURIComponent(frm.doc.name) +
		"&format=" +
		encodeURIComponent(format) +
		"&no_letterhead=1&trigger_print=0";
	window.open(url, "_blank");
}

// Answering Yes means this must be a formal NCR: offer Escalate to NCR straight away.
// The Yes is not saved on the Rework; escalating records it, cancelling clears it.
function hse_eval_changed(frm, fieldname) {
	if (frm.doc[fieldname] !== "Yes" || frm.doc.record_type !== "Rework") return;
	const crit = fieldname.slice(3);
	const preset = HSE_RW_EVAL.filter((f) => frm.doc[f] === "Yes").map((f) => f.slice(3));
	frm.set_value(
		HSE_RW_EVAL.filter((f) => frm.doc[f] === "Yes").reduce((o, f) => ((o[f] = ""), o), {})
	).then(() => {
		if (frm.is_new()) {
			frappe.msgprint(
				__("Save the Rework first, then answer Yes to escalate it to an NCR.")
			);
			return;
		}
		const go = () => hse_escalate_dialog(frm, preset.length ? preset : [crit]);
		if (frm.is_dirty()) frm.save().then(go);
		else go();
	});
}

function hse_escalate_dialog(frm, preset = []) {
	const d = new frappe.ui.Dialog({
		title: __("Escalate {0} to an NCR", [frm.doc.name]),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p class="text-muted">${__(
					"Tick each QM-104 in-house NCR criterion that applies. A formal NCR is raised with the details, cause and links from this Rework, and this Rework is closed as Cancelled. The unit stays on QC Hold until the NCR is resolved."
				)}</p>`,
			},
			...HSE_NCR_CRITERIA.map(([fieldname, label]) => ({
				fieldname,
				label,
				fieldtype: "Check",
				default: preset.includes(fieldname) ? 1 : 0,
			})),
			{ fieldname: "reason", label: __("Reason for escalation"), fieldtype: "Small Text" },
		],
		primary_action_label: __("Escalate to NCR"),
		primary_action(values) {
			const criteria = HSE_NCR_CRITERIA.map(([f]) => f).filter((f) => values[f]);
			if (!criteria.length) {
				frappe.msgprint(__("Select at least one QM-104 NCR criterion that applies."));
				return;
			}
			frappe.call({
				method: "hse.quality_metrics.rework.escalate_to_ncr",
				args: { name: frm.doc.name, criteria, reason: values.reason },
				freeze: true,
				callback: (r) => {
					d.hide();
					if (r.message) frappe.set_route("Form", "Nonconformance Report", r.message);
				},
			});
		},
	});
	d.show();
}
