frappe.listview_settings["QC Inspection"] = {
	add_fields: ["status", "docstatus", "stage", "shop"],
	get_indicator(doc) {
		if (doc.docstatus === 0) return [__("Draft"), "gray", "docstatus,=,0"];
		if (doc.docstatus === 2) return [__("Cancelled"), "red", "docstatus,=,2"];
		if (doc.status === "Accepted") return [__("Accepted"), "green", "status,=,Accepted"];
		if (doc.status === "Rejected") return [__("Rejected"), "red", "status,=,Rejected"];
		return [__(doc.status), "orange", `status,=,${doc.status}`];
	},
};
