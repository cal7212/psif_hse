// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.listview_settings["Training Role"] = {
	onload(listview) {
		if (!frappe.user.has_role(["System Manager", "HR Manager", "Training Coordinator"]))
			return;
		listview.page.add_inner_button(__("Re-sync All Employees"), () =>
			frappe.call("hse.training_matrix.matrix.resync_all_matrices")
		);
	},
};
