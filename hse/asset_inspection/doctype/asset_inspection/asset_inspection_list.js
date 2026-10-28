frappe.listview_settings["Asset Inspection"] = {
	add_fields: ["status", "docstatus"],
	onload(listview) {
		// Quick Add Asset lives in hse/public/js/quick_asset.js (loaded for this list in hooks.py).
		if (!frappe.model.can_create("Asset") || !window.hse || !window.hse.quick_asset) return;
		listview.page.add_inner_button(__("Quick Add Asset"), () => {
			window.hse.quick_asset.open((name) =>
				frappe.new_doc("Asset Inspection", { asset: name })
			);
		});
	},
	get_indicator(doc) {
		if (doc.docstatus === 0) return [__("Draft"), "gray", "docstatus,=,0"];
		if (doc.docstatus === 2) return [__("Cancelled"), "red", "docstatus,=,2"];
		if (doc.status === "Accepted") return [__("Accepted"), "green", "status,=,Accepted"];
		if (doc.status === "Rejected") return [__("Rejected"), "red", "status,=,Rejected"];
		return [__(doc.status), "orange", `status,=,${doc.status}`];
	},
};
