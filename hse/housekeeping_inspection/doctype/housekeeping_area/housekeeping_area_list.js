frappe.listview_settings["Housekeeping Area"] = {
	add_fields: ["housekeeping_status", "schedule_status", "disabled"],
	get_indicator(doc) {
		if (doc.disabled) return [__("Disabled"), "gray", "disabled,=,1"];
		if (doc.housekeeping_status === "Hazard Open") return [__("Hazard Open"), "red", "housekeeping_status,=,Hazard Open"];
		if (doc.schedule_status === "Overdue") return [__("Overdue"), "orange", "schedule_status,=,Overdue"];
		if (doc.housekeeping_status === "Action Required") return [__("Action Required"), "yellow", "housekeeping_status,=,Action Required"];
		if (doc.schedule_status === "Due") return [__("Due Today"), "blue", "schedule_status,=,Due"];
		return [__("Satisfactory"), "green", "housekeeping_status,=,Satisfactory"];
	},
};
