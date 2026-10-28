// Adds Quick Add Asset to the Asset list without replacing ERPNext's list settings.
frappe.listview_settings["Asset"] = frappe.listview_settings["Asset"] || {};
(function (settings) {
	const erpnext_onload = settings.onload;
	settings.onload = function (listview) {
		if (erpnext_onload) erpnext_onload.call(this, listview);
		if (!frappe.model.can_create("Asset")) return;
		listview.page.add_inner_button(__("Quick Add Asset"), () => {
			window.hse.quick_asset.open((name) => {
				listview.refresh();
				frappe.set_route("Form", "Asset", name);
			});
		});
	};
})(frappe.listview_settings["Asset"]);
