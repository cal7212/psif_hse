// QM-104 Rev. 3 Rework on Non Conformance (loaded alongside non_conformance.js)
const HSE_NCR_CRITERIA = [
	["crit_scrap", __("Results in scrap of a finished part")],
	[
		"crit_cannot_rework",
		__(
			"Can't be reworked to the drawing or spec (needs use-as-is, repair or deviation per QM-144, or Engineering or customer approval)"
		),
	],
	["crit_customer_safety", __("Affects a customer requirement, safety or the promised ship date")],
	["crit_supplier", __("Supplier caused or contributed, or suspected counterfeit (QM-134 / QM-310)")],
];

frappe.ui.form.on("Non Conformance", {
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
				() => frappe.set_route("Form", "Non Conformance", frm.doc.escalated_to),
				__("View")
			);
			frm.dashboard.set_headline_alert(
				__("This Rework was escalated to NCR {0}.", [frm.doc.escalated_to]),
				"blue"
			);
		} else if (frm.doc.escalated_from) {
			frm.add_custom_button(
				__("Rework {0}", [frm.doc.escalated_from]),
				() => frappe.set_route("Form", "Non Conformance", frm.doc.escalated_from),
				__("View")
			);
		}

		if (rework && frm.doc.status === "Open" && frm.perm[0] && frm.perm[0].write) {
			frm.add_custom_button(__("Escalate to NCR"), () => hse_escalate_dialog(frm), __("Create"));
		}
	},
});

function hse_rework_print_format(frm) {
	frm.meta.default_print_format =
		frm.doc.record_type === "Rework" ? "QM-104 Rework Report" : "QM-104 Non-Conformance Report";
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

function hse_escalate_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Escalate {0} to an NCR", [frm.doc.name]),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p class="text-muted">${__(
					"Tick each QM-104 in-house NCR criterion that applies. A formal NCR is raised with the details, cause and links from this Rework, and this Rework is closed as Cancelled. The unit stays on QC Hold until the NCR is resolved."
				)}</p>`,
			},
			...HSE_NCR_CRITERIA.map(([fieldname, label]) => ({ fieldname, label, fieldtype: "Check" })),
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
					if (r.message) frappe.set_route("Form", "Non Conformance", r.message);
				},
			});
		},
	});
	d.show();
}
