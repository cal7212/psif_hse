# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Quick Add Asset: create and submit an ERPNext Asset without purchase details.

The asset is an Existing Asset with depreciation off, so no purchase receipt or
invoice is needed. ERPNext still requires a Net Purchase Amount; the placeholder
comes from HSE Asset Settings.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, getdate, nowdate

SETTINGS = "HSE Asset Settings"
EXISTING_ASSET = "Existing Asset"


def placeholder_amount() -> float:
	"""Placeholder Net Purchase Amount: the saved setting, else the field default."""
	# A blank or zero setting can't be used (ERPNext requires a Net Purchase Amount),
	# so it falls back to the field default.
	amount = flt(frappe.db.get_single_value(SETTINGS, "placeholder_purchase_amount"))
	if amount <= 0:
		amount = flt(frappe.get_meta(SETTINGS).get_field("placeholder_purchase_amount").default)
	if amount <= 0:
		frappe.throw(_("Set a Placeholder Purchase Amount above zero in HSE Asset Settings."))
	return amount


def default_company() -> str | None:
	company = frappe.defaults.get_user_default("Company")
	if company:
		return company
	companies = frappe.get_all("Company", pluck="name", limit=2)
	return companies[0] if len(companies) == 1 else None


@frappe.whitelist()
def get_defaults() -> dict:
	"""Values the Quick Add dialog starts with."""
	return {
		"company": default_company(),
		"location": frappe.db.get_single_value(SETTINGS, "default_location"),
		"in_service_date": nowdate(),
		"placeholder_amount": placeholder_amount(),
	}


def build_asset_values(
	item: dict,
	asset_name: str,
	location: str,
	in_service_date: str,
	company: str,
	amount: float,
	custodian: str | None = None,
	department: str | None = None,
	maintenance_required: int = 0,
) -> dict:
	"""The Asset fields Quick Add sets. Kept separate so it can be unit tested."""
	values = {
		"doctype": "Asset",
		"company": company,
		"item_code": item["name"],
		"asset_name": cstr(asset_name).strip() or item.get("item_name") or item["name"],
		"asset_category": item.get("asset_category"),
		"location": location,
		"asset_type": EXISTING_ASSET,
		"calculate_depreciation": 0,
		"purchase_date": in_service_date,
		"available_for_use_date": in_service_date,
		"net_purchase_amount": amount,
		"asset_quantity": 1,
		"maintenance_required": cint(maintenance_required),
	}
	if custodian:
		values["custodian"] = custodian
	if department:
		values["department"] = department
	return values


def get_asset_item(item_code: str) -> dict:
	item = frappe.db.get_value(
		"Item",
		item_code,
		["name", "item_name", "asset_category", "is_fixed_asset", "is_stock_item", "disabled"],
		as_dict=True,
	)
	if not item:
		frappe.throw(_("Item {0} does not exist.").format(item_code))
	if not item.is_fixed_asset or item.is_stock_item or item.disabled:
		frappe.throw(_("Item {0} must be an enabled, non-stock Fixed Asset item.").format(item_code))
	if not item.asset_category:
		frappe.throw(_("Item {0} has no Asset Category.").format(item_code))
	return item


def create_asset_item(item_code: str, item_name: str, asset_category: str) -> dict:
	"""Create a new asset type (Item), copying Item Group and UOM from an item in the same category."""
	item_code = cstr(item_code).strip()
	if not item_code or not cstr(item_name).strip() or not asset_category:
		frappe.throw(_("Enter the Item Code, Item Name and Asset Category for the new asset type."))
	if frappe.db.exists("Item", item_code):
		frappe.throw(_("Item {0} already exists. Pick it under Asset Type instead.").format(item_code))
	template = frappe.db.get_value(
		"Item",
		{"is_fixed_asset": 1, "asset_category": asset_category, "disabled": 0},
		["item_group", "stock_uom"],
		as_dict=True,
		order_by="creation desc",
	) or frappe.db.get_value(
		"Item",
		{"is_fixed_asset": 1, "disabled": 0},
		["item_group", "stock_uom"],
		as_dict=True,
		order_by="creation desc",
	)
	if not template:
		frappe.throw(_("Create the first Fixed Asset item in Stock, then Quick Add can copy its settings."))
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": cstr(item_name).strip(),
			"item_group": template.item_group,
			"stock_uom": template.stock_uom,
			"is_stock_item": 0,
			"is_fixed_asset": 1,
			"asset_category": asset_category,
		}
	).insert()
	return get_asset_item(item_code)


@frappe.whitelist(methods=["POST"])
def create_asset(
	asset_name: str,
	location: str,
	in_service_date: str,
	company: str | None = None,
	item_code: str | None = None,
	new_item: int = 0,
	new_item_code: str | None = None,
	new_item_name: str | None = None,
	asset_category: str | None = None,
	custodian: str | None = None,
	department: str | None = None,
	maintenance_required: int = 0,
) -> str:
	"""Create and submit an Existing Asset. Normal Asset (and Item) permissions apply."""
	frappe.has_permission("Asset", "create", throw=True)
	frappe.has_permission("Asset", "submit", throw=True)
	company = company or default_company()
	if not company:
		frappe.throw(_("Select a Company."))
	if not location:
		frappe.throw(_("Select a Location."))
	if not in_service_date:
		frappe.throw(_("Enter the In-Service Date."))
	if getdate(in_service_date) > getdate(nowdate()):
		frappe.throw(_("In-Service Date cannot be in the future."))

	if cint(new_item):
		item = create_asset_item(new_item_code, new_item_name, asset_category)
	else:
		if not item_code:
			frappe.throw(_("Select an Asset Type, or tick New Asset Type."))
		item = get_asset_item(item_code)

	asset = frappe.get_doc(
		build_asset_values(
			item,
			asset_name,
			location,
			in_service_date,
			company,
			placeholder_amount(),
			custodian=custodian,
			department=department,
			maintenance_required=maintenance_required,
		)
	)
	asset.insert()
	asset.submit()
	asset.add_comment("Info", _("Created with Quick Add Asset (no purchase details)."))
	return asset.name
