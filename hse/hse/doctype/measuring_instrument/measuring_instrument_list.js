frappe.listview_settings["Measuring Instrument"] = {
	add_fields: ["status", "calibration_due", "calibration_required"],
	get_indicator(doc) {
		if (doc.status !== "Active") return [__(doc.status), "gray", "status,=," + doc.status];
		if (!doc.calibration_required)
			return [__("Verify Before Use"), "blue", "calibration_required,=,0"];
		if (!doc.calibration_due)
			return [__("No Cal Date"), "orange", "calibration_due,is,not set"];
		const days = frappe.datetime.get_diff(doc.calibration_due, frappe.datetime.get_today());
		if (days < 0)
			return [__("Overdue"), "red", "calibration_due,<," + frappe.datetime.get_today()];
		if (days <= 30) return [__("Due Soon"), "orange", "status,=,Active"];
		return [__("In Calibration"), "green", "status,=,Active"];
	},
};
