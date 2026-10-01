frappe.listview_settings["SDS"] = {
	add_fields: ["status", "sds_uploaded", "attach_sds"],
	get_indicator(doc) {
		if (doc.status === "Active" && (doc.sds_uploaded || !doc.attach_sds)) {
			return [__("Needs SDS"), "red", "sds_uploaded,=,1"];
		}
		const colors = { Active: "green", Superseded: "gray", Discontinued: "orange" };
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
