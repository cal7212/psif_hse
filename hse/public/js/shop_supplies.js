// Shop Supplies: short forms over ERPNext Stock (hse/hse/supplies.py).
// Used by the Item, Stock Entry and Stock Reconciliation lists and the QC Unit form.
frappe.provide("hse.supplies");

(function (supplies) {
	const API = "hse.hse.supplies.";
	const item_query = () => ({
		filters: { is_stock_item: 1, has_serial_no: 0, has_batch_no: 0, disabled: 0 },
	});

	function defaults() {
		return frappe.call(API + "get_defaults").then((r) => r.message || {});
	}

	function header_fields(d0, extra) {
		return [
			{
				fieldname: "warehouse",
				fieldtype: "Link",
				label: __("Warehouse"),
				options: "Warehouse",
				reqd: 1,
				default: d0.warehouse,
				get_query: () => ({ filters: { is_group: 0, disabled: 0, company: d0.company } }),
			},
			{
				fieldname: "posting_date",
				fieldtype: "Date",
				label: __("Posting Date"),
				reqd: 1,
				default: d0.posting_date,
			},
			{ fieldtype: "Column Break" },
			...(extra || []),
			{ fieldtype: "Section Break" },
		];
	}

	// Fill a table row from the item's current rate / on-hand quantity.
	function fill_row(dialog, row, set) {
		const warehouse = dialog.get_value("warehouse");
		if (!row || !row.item_code) return;
		frappe
			.call(API + "get_item_info", { item_code: row.item_code, warehouse: warehouse })
			.then((r) => {
				const info = r.message || {};
				set(row, info);
				dialog.fields_dict.items.grid.refresh();
			});
	}

	function run(dialog, method, args, done) {
		dialog.disable_primary_action();
		return frappe
			.call({ method: API + method, args: args, freeze: true })
			.then((r) => {
				dialog.hide();
				done(r.message);
			})
			.always(() => dialog.enable_primary_action());
	}

	function rows(values) {
		return (values.items || []).filter((r) => r.item_code);
	}

	function open_doc(doctype, name, verb) {
		frappe.show_alert({
			message: __("{0} {1} {2}.", [__(doctype), name, verb]),
			indicator: "green",
		});
		frappe.set_route("Form", doctype, name);
	}

	supplies.receive = function () {
		defaults().then((d0) => {
			const dialog = new frappe.ui.Dialog({
				title: __("Receive Supplies"),
				size: "large",
				fields: [
					...header_fields(d0, [
						{
							fieldname: "company",
							fieldtype: "Link",
							label: __("Company"),
							options: "Company",
							reqd: 1,
							default: d0.company,
						},
						{ fieldname: "note", fieldtype: "Small Text", label: __("Note") },
					]),
					{
						fieldname: "items",
						fieldtype: "Table",
						label: __("Items"),
						in_place_edit: true,
						reqd: 1,
						data: [{}],
						fields: [
							{
								fieldname: "item_code",
								fieldtype: "Link",
								label: __("Item"),
								options: "Item",
								in_list_view: 1,
								reqd: 1,
								get_query: item_query,
								onchange() {
									fill_row(dialog, this.doc, (row, info) => {
										if (!flt(row.rate)) row.rate = info.rate;
									});
								},
							},
							{
								fieldname: "qty",
								fieldtype: "Float",
								label: __("Qty"),
								in_list_view: 1,
								reqd: 1,
							},
							{
								fieldname: "rate",
								fieldtype: "Currency",
								label: __("Unit Cost"),
								in_list_view: 1,
								description: __(
									"Filled with the current rate. Blank uses the current rate."
								),
							},
						],
					},
				],
				primary_action_label: __("Receive"),
				primary_action(v) {
					run(
						dialog,
						"receive",
						{
							warehouse: v.warehouse,
							items: rows(v),
							company: v.company,
							posting_date: v.posting_date,
							note: v.note,
						},
						(name) => open_doc("Stock Entry", name, __("submitted"))
					);
				},
			});
			dialog.show();
		});
	};

	supplies.issue = function (preset) {
		preset = preset || {};
		defaults().then((d0) => {
			const dialog = new frappe.ui.Dialog({
				title: __("Issue Supplies"),
				size: "large",
				fields: [
					...header_fields(d0, [
						{
							fieldname: "issued_to",
							fieldtype: "Link",
							label: __("Issued To"),
							options: "Employee",
							reqd: 1,
						},
						{
							fieldname: "qc_unit",
							fieldtype: "Link",
							label: __("QC Unit (Work Order)"),
							options: "QC Unit",
							default: preset.qc_unit,
							description: __("Optional. Search by TrulinX Work Order."),
						},
						{ fieldname: "note", fieldtype: "Small Text", label: __("Note") },
						{
							fieldname: "company",
							fieldtype: "Link",
							label: __("Company"),
							options: "Company",
							reqd: 1,
							default: d0.company,
							hidden: 1,
						},
					]),
					{
						fieldname: "items",
						fieldtype: "Table",
						label: __("Items"),
						in_place_edit: true,
						reqd: 1,
						data: [{}],
						fields: [
							{
								fieldname: "item_code",
								fieldtype: "Link",
								label: __("Item"),
								options: "Item",
								in_list_view: 1,
								reqd: 1,
								get_query: item_query,
								onchange() {
									fill_row(dialog, this.doc, (row, info) => {
										row.on_hand = info.on_hand;
									});
								},
							},
							{
								fieldname: "qty",
								fieldtype: "Float",
								label: __("Qty"),
								in_list_view: 1,
								reqd: 1,
							},
							{
								fieldname: "on_hand",
								fieldtype: "Float",
								label: __("On Hand"),
								in_list_view: 1,
								read_only: 1,
							},
						],
					},
				],
				primary_action_label: __("Issue"),
				primary_action(v) {
					run(
						dialog,
						"issue",
						{
							warehouse: v.warehouse,
							items: rows(v),
							issued_to: v.issued_to,
							qc_unit: v.qc_unit,
							note: v.note,
							company: v.company,
							posting_date: v.posting_date,
						},
						(name) => {
							if (preset.after_issue) {
								frappe.show_alert({
									message: __("Stock Entry {0} submitted.", [name]),
									indicator: "green",
								});
								preset.after_issue(name);
							} else {
								open_doc("Stock Entry", name, __("submitted"));
							}
						}
					);
				},
			});
			dialog.show();
		});
	};

	supplies.count = function () {
		defaults().then((d0) => {
			const dialog = new frappe.ui.Dialog({
				title: __("Count Supplies"),
				size: "large",
				fields: [
					...header_fields(d0, [
						{
							fieldname: "company",
							fieldtype: "Link",
							label: __("Company"),
							options: "Company",
							reqd: 1,
							default: d0.company,
						},
						{ fieldname: "note", fieldtype: "Small Text", label: __("Note") },
					]),
					{
						fieldtype: "HTML",
						options: `<p class="text-muted small">${__(
							"Enter what is on the shelf. Only rows that differ from the system quantity are posted, at the current rate."
						)}</p>`,
					},
					{
						fieldname: "items",
						fieldtype: "Table",
						label: __("Items"),
						in_place_edit: true,
						reqd: 1,
						data: [{}],
						fields: [
							{
								fieldname: "item_code",
								fieldtype: "Link",
								label: __("Item"),
								options: "Item",
								in_list_view: 1,
								reqd: 1,
								get_query: item_query,
								onchange() {
									fill_row(dialog, this.doc, (row, info) => {
										row.on_hand = info.on_hand;
									});
								},
							},
							{
								fieldname: "on_hand",
								fieldtype: "Float",
								label: __("System Qty"),
								in_list_view: 1,
								read_only: 1,
							},
							{
								fieldname: "qty",
								fieldtype: "Float",
								label: __("Counted Qty"),
								in_list_view: 1,
								reqd: 1,
							},
						],
					},
				],
				primary_action_label: __("Post Count"),
				primary_action(v) {
					run(
						dialog,
						"count",
						{
							warehouse: v.warehouse,
							items: rows(v),
							company: v.company,
							posting_date: v.posting_date,
							note: v.note,
						},
						(name) => {
							if (name) open_doc("Stock Reconciliation", name, __("submitted"));
							else
								frappe.msgprint(
									__(
										"Every counted quantity matches the system. Nothing was posted."
									)
								);
						}
					);
				},
			});
			dialog.show();
		});
	};

	supplies.add_item = function () {
		defaults().then((d0) => {
			const dialog = new frappe.ui.Dialog({
				title: __("Add Supply Item"),
				fields: [
					{ fieldname: "item_code", fieldtype: "Data", label: __("Item Code"), reqd: 1 },
					{ fieldname: "item_name", fieldtype: "Data", label: __("Item Name"), reqd: 1 },
					{
						fieldname: "item_group",
						fieldtype: "Link",
						label: __("Item Group"),
						options: "Item Group",
						reqd: 1,
						default: d0.item_group,
						get_query: () => ({ filters: { is_group: 0 } }),
					},
					{
						fieldname: "stock_uom",
						fieldtype: "Link",
						label: __("UOM"),
						options: "UOM",
						reqd: 1,
						default: d0.stock_uom,
					},
					{ fieldtype: "Column Break" },
					{
						fieldname: "warehouse",
						fieldtype: "Link",
						label: __("Default Warehouse"),
						options: "Warehouse",
						default: d0.warehouse,
						get_query: () => ({
							filters: { is_group: 0, disabled: 0, company: d0.company },
						}),
					},
					{
						fieldname: "reorder_level",
						fieldtype: "Float",
						label: __("Reorder Level"),
						description: __("Optional. Reorder when stock falls to this."),
					},
					{
						fieldname: "reorder_qty",
						fieldtype: "Float",
						label: __("Reorder Qty"),
						depends_on: "eval:doc.reorder_level",
					},
					{ fieldtype: "Section Break", label: __("Opening Quantity (optional)") },
					{ fieldname: "opening_qty", fieldtype: "Float", label: __("Opening Qty") },
					{ fieldtype: "Column Break" },
					{
						fieldname: "unit_cost",
						fieldtype: "Currency",
						label: __("Unit Cost"),
						depends_on: "eval:doc.opening_qty",
						description: __("Blank posts the opening quantity at zero cost."),
					},
					{
						fieldname: "company",
						fieldtype: "Link",
						label: __("Company"),
						options: "Company",
						reqd: 1,
						default: d0.company,
						hidden: 1,
					},
				],
				primary_action_label: __("Add Item"),
				primary_action(v) {
					run(dialog, "add_item", v, (res) => {
						let msg = __("Item {0} added.", [res.item]);
						if (res.receipt)
							msg += " " + __("Opening quantity received on {0}.", [res.receipt]);
						frappe.show_alert({ message: msg, indicator: "green" });
						frappe.set_route("Form", "Item", res.item);
					});
				},
			});
			dialog.show();
		});
	};

	// Adds the "Shop Supplies" button group to a list view.
	supplies.add_list_buttons = function (listview) {
		const group = __("Shop Supplies");
		if (frappe.model.can_create("Item")) {
			listview.page.add_inner_button(__("Add Supply Item"), supplies.add_item, group);
		}
		if (frappe.model.can_create("Stock Entry")) {
			listview.page.add_inner_button(__("Receive"), supplies.receive, group);
			listview.page.add_inner_button(__("Issue"), () => supplies.issue(), group);
		}
		if (frappe.model.can_create("Stock Reconciliation")) {
			listview.page.add_inner_button(__("Count"), supplies.count, group);
		}
	};

	// Wraps a list's onload without replacing ERPNext's own list settings.
	supplies.extend_list = function (doctype) {
		const settings = (frappe.listview_settings[doctype] =
			frappe.listview_settings[doctype] || {});
		if (settings.__hse_supplies) return;
		settings.__hse_supplies = true;
		const original = settings.onload;
		settings.onload = function (listview) {
			if (original) original.call(this, listview);
			supplies.add_list_buttons(listview);
		};
	};
})(window.hse.supplies);
