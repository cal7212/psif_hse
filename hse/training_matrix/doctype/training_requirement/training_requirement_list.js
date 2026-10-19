// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const TM_SETUP = "hse.training_matrix.setup.appendix_a";
const TM_MATRIX = "hse.training_matrix.matrix";

frappe.listview_settings["Training Requirement"] = {
	add_fields: ["disabled", "all_employees", "high_hazard"],
	get_indicator(doc) {
		if (doc.disabled) return [__("Disabled"), "gray", "disabled,=,1"];
		if (doc.high_hazard) return [__("High Hazard"), "orange", "high_hazard,=,1"];
		if (doc.all_employees) return [__("All Employees"), "blue", "all_employees,=,1"];
		return [__("By Role"), "green", "all_employees,=,0"];
	},
	onload(listview) {
		if (!frappe.user.has_role(["System Manager", "HR Manager", "Training Coordinator"]))
			return;
		listview.page.add_inner_button(
			__("Load TRN-700 Appendix A"),
			() =>
				frappe.confirm(
					__(
						"Create the four Training Roles and the HR, Safety and QMS courses from TRN-700 Rev 1 Appendix A? Existing records are not changed."
					),
					() =>
						frappe
							.call({ method: `${TM_SETUP}.load_appendix_a`, freeze: true })
							.then(() => listview.refresh())
				),
			__("Training Matrix")
		);
		listview.page.add_inner_button(
			__("Re-sync All Employees"),
			() => frappe.call(`${TM_MATRIX}.resync_all_matrices`),
			__("Training Matrix")
		);
	},
};
