// Quality Goal list: create the HSE starter goals from the desk (hse.quality_metrics)
frappe.listview_settings["Quality Goal"] = Object.assign(
	frappe.listview_settings["Quality Goal"] || {},
	{
		onload(listview) {
			if (!frappe.user.has_role(["Quality Manager", "System Manager"])) return;

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
