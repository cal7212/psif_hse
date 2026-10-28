// Quick Add Asset: a short form that creates and submits an Existing Asset
// without purchase details. Shared by the Asset and Asset Inspection lists.
frappe.provide("hse.quick_asset");

window.hse.quick_asset.open = function (after_create) {
	frappe.call("hse.asset_inspection.quick_asset.get_defaults").then((r) => {
		const defaults = r.message || {};
		const d = new frappe.ui.Dialog({
			title: __("Quick Add Asset"),
			fields: [
				{
					fieldtype: "HTML",
					options: `<p class="text-muted small">${__(
						"Creates and submits an Existing Asset with depreciation off. Net Purchase Amount is set to {0} from HSE Asset Settings.",
						[format_currency(defaults.placeholder_amount)]
					)}</p>`,
				},
				{
					fieldname: "item_code",
					fieldtype: "Link",
					label: __("Asset Type (Item)"),
					options: "Item",
					depends_on: "eval:!doc.new_item",
					mandatory_depends_on: "eval:!doc.new_item",
					get_query: () => ({
						filters: { is_fixed_asset: 1, is_stock_item: 0, disabled: 0 },
					}),
					onchange() {
						const item = d.get_value("item_code");
						if (!item || d.get_value("asset_name")) return;
						frappe.db.get_value("Item", item, "item_name").then((res) => {
							if (!d.get_value("asset_name")) {
								d.set_value("asset_name", res.message && res.message.item_name);
							}
						});
					},
				},
				{
					fieldname: "new_item",
					fieldtype: "Check",
					label: __("New Asset Type"),
					description: __(
						"Tick if no existing item fits. A new Fixed Asset item is created."
					),
				},
				{
					fieldname: "new_item_code",
					fieldtype: "Data",
					label: __("Item Code"),
					depends_on: "eval:doc.new_item",
					mandatory_depends_on: "eval:doc.new_item",
				},
				{
					fieldname: "new_item_name",
					fieldtype: "Data",
					label: __("Item Name"),
					depends_on: "eval:doc.new_item",
					mandatory_depends_on: "eval:doc.new_item",
				},
				{
					fieldname: "asset_category",
					fieldtype: "Link",
					label: __("Asset Category"),
					options: "Asset Category",
					depends_on: "eval:doc.new_item",
					mandatory_depends_on: "eval:doc.new_item",
				},
				{ fieldtype: "Section Break" },
				{
					fieldname: "asset_name",
					fieldtype: "Data",
					label: __("Asset Name"),
					reqd: 1,
				},
				{
					fieldname: "location",
					fieldtype: "Link",
					label: __("Location"),
					options: "Location",
					reqd: 1,
					default: defaults.location,
				},
				{
					fieldname: "in_service_date",
					fieldtype: "Date",
					label: __("In-Service Date"),
					reqd: 1,
					default: defaults.in_service_date,
					description: __("Used as the purchase and available-for-use dates."),
				},
				{ fieldtype: "Column Break" },
				{
					fieldname: "company",
					fieldtype: "Link",
					label: __("Company"),
					options: "Company",
					reqd: 1,
					default: defaults.company,
				},
				{
					fieldname: "custodian",
					fieldtype: "Link",
					label: __("Custodian"),
					options: "Employee",
				},
				{
					fieldname: "department",
					fieldtype: "Link",
					label: __("Department"),
					options: "Department",
				},
				{
					fieldname: "maintenance_required",
					fieldtype: "Check",
					label: __("Maintenance Required"),
					default: 1,
				},
			],
			primary_action_label: __("Create Asset"),
			primary_action(values) {
				d.disable_primary_action();
				frappe
					.call({
						method: "hse.asset_inspection.quick_asset.create_asset",
						args: values,
						freeze: true,
						freeze_message: __("Creating asset..."),
					})
					.then((res) => {
						d.hide();
						const name = res.message;
						frappe.show_alert({
							message: __("Asset {0} created.", [name]),
							indicator: "green",
						});
						if (after_create) after_create(name);
						else frappe.set_route("Form", "Asset", name);
					})
					.always(() => d.enable_primary_action());
			},
		});
		d.show();
	});
};
