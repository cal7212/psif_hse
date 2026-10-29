// Quality Goal list: create the HSE starter goals from the desk (hse.quality_metrics)
frappe.listview_settings["Quality Goal"] = Object.assign(
	frappe.listview_settings["Quality Goal"] || {},
	{
		onload(listview) {
			if (!frappe.user.has_role(["Quality Manager", "System Manager"])) return;

			listview.page.add_inner_button(__("First Pass Yield by Stage"), () =>
				window.hse_stage_fpy_dialog(listview)
			);

			frappe.call({
				method: "hse.quality_metrics.events.get_missing_starter_goals",
				callback: (r) => {
					const missing = r.message || [];
					if (!missing.length) return;

					listview.page.add_inner_button(__("Create Starter Goals"), () => {
						frappe.confirm(
							__(
								"Create these monthly Quality Goals with calculated metrics and example targets?<br><br>{0}<br><br>Reviews are created on the 1st of each month for the previous month. Edit the targets to suit your program.",
								[
									missing
										.map((g) => `&bull; ${frappe.utils.escape_html(g)}`)
										.join("<br>"),
								]
							),
							() =>
								frappe.call({
									method: "hse.quality_metrics.events.create_starter_goals",
									freeze: true,
									freeze_message: __("Creating Quality Goals..."),
									callback: (res) => {
										const created = (res.message && res.message.created) || [];
										frappe.show_alert({
											message: created.length
												? __("Created {0} Quality Goal(s): {1}", [
														created.length,
														created.join(", "),
												  ])
												: __("All starter goals already exist."),
											indicator: "green",
										});
										listview.page.remove_inner_button(
											__("Create Starter Goals")
										);
										listview.refresh();
									},
								})
						);
					});
				},
			});
		},
	}
);

// One Quality Goal per shop with a first-pass-yield objective for each enabled QC Stage
window.hse_stage_fpy_dialog = function (listview) {
	const d = new frappe.ui.Dialog({
		title: __("First Pass Yield by Stage"),
		fields: [
			{
				fieldtype: "HTML",
				options: `<p class="text-muted">${__(
					"Creates one Quality Goal per shop (for example First Pass Yield by Stage - HPU) with a row for each enabled QC Stage. If the goals already exist, only stages they are missing are added."
				)}</p>`,
			},
			{
				fieldname: "target",
				fieldtype: "Percent",
				label: __("Target first-pass yield (%)"),
				description: __(
					"Leave blank to record the values without Pass/Fail. You can change each stage's target on the goal later."
				),
			},
			{
				fieldname: "frequency",
				fieldtype: "Select",
				label: __("Review Frequency"),
				options: "Monthly\nWeekly\nQuarterly",
				default: "Monthly",
				reqd: 1,
			},
		],
		primary_action_label: __("Create"),
		primary_action(values) {
			frappe.call({
				method: "hse.quality_metrics.events.create_stage_fpy_goals",
				args: {
					target: values.target ? values.target : "",
					frequency: values.frequency,
				},
				freeze: true,
				freeze_message: __("Creating Quality Goals..."),
				callback: (r) => {
					d.hide();
					const m = r.message || {};
					const created = m.created || [];
					const updated = m.updated || [];
					const lines = [];
					if (created.length) lines.push(__("Created: {0}", [created.join(", ")]));
					if (updated.length)
						lines.push(__("Added new stages to: {0}", [updated.join(", ")]));
					frappe.msgprint(
						lines.length ? lines.join("<br>") : __("All stage goals are up to date.")
					);
					listview.refresh();
				},
			});
		},
	});
	d.show();
};
