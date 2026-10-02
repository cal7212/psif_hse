// Calculated metrics on Quality Goal (hse.quality_metrics)
frappe.ui.form.on("Quality Goal Objective", {
	hse_metric(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.hse_metric) return;
		frappe.call({
			method: "hse.quality_metrics.events.get_metric_choices",
			callback: (r) => {
				const m = (r.message || []).find((x) => x.value === row.hse_metric);
				if (!m) return;
				if (!row.objective) frappe.model.set_value(cdt, cdn, "objective", m.label);
				if (!row.target_operator)
					frappe.model.set_value(cdt, cdn, "target_operator", "Record only");
			},
		});
	},
});
