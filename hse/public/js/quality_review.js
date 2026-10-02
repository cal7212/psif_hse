// Calculated metrics on Quality Review (hse.quality_metrics)
frappe.ui.form.on("Quality Review", {
	refresh(frm) {
		const has_metrics = (frm.doc.reviews || []).some((r) => r.hse_metric);
		if (frm.is_new() || !has_metrics) return;

		frm.add_custom_button(__("Recalculate Metrics"), () => {
			frappe.confirm(
				__(
					"Recalculate every calculated objective for {0} to {1}? Pass/Fail on those objectives will be reset from the new values.",
					[frappe.datetime.str_to_user(frm.doc.period_start), frappe.datetime.str_to_user(frm.doc.period_end)]
				),
				() =>
					frappe.call({
						method: "hse.quality_metrics.events.recalculate_review",
						args: { review: frm.doc.name },
						freeze: true,
						callback: () => frm.reload_doc(),
					})
			);
		});

		if (frm.doc.metrics_calculated_on) {
			frm.set_intro(
				__("Calculated objectives for {0} to {1}, last calculated {2}. Add comments in each objective's Review field.", [
					frappe.datetime.str_to_user(frm.doc.period_start),
					frappe.datetime.str_to_user(frm.doc.period_end),
					frappe.datetime.str_to_user(frm.doc.metrics_calculated_on),
				]),
				"blue"
			);
		}
	},
});
