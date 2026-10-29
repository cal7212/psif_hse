# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Shop Supplies: short forms over ERPNext Stock for non-inventory shop supplies.

Each form creates and submits a normal ERPNext document:
  Add Supply Item -> Item (stock item), plus a Material Receipt for any opening qty
  Receive         -> Stock Entry (Material Receipt)
  Issue           -> Stock Entry (Material Issue), with Issued To, QC Unit and note
  Count           -> Stock Reconciliation for counted quantities that differ
  Flag for Reorder -> draft Purchase Material Request (one open draft per warehouse)
Issue, Count and Flag for Reorder accept a camera or typed barcode scan. New stock items get a
barcode equal to their item code, and the Supply Label 2x4 print format prints it as a QR code.
Normal Item / Stock Entry / Stock Reconciliation permissions apply.
"""

import base64
import json

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cstr, escape_html, flt, getdate, nowdate

SETTINGS = "Shop Supplies Settings"
MODULE = "HSE"


# ------------------------------------------------------------------ setup
def get_custom_fields() -> dict:
	return {
		"Stock Entry": [
			{
				"fieldname": "issued_to",
				"label": "Issued To",
				"fieldtype": "Link",
				"options": "Employee",
				"insert_after": "stock_entry_type",
				"depends_on": "eval:doc.purpose=='Material Issue'",
				"description": "Shop Supplies: who took the supplies.",
			},
			{
				"fieldname": "qc_unit",
				"label": "QC Unit",
				"fieldtype": "Link",
				"options": "QC Unit",
				"insert_after": "issued_to",
				"depends_on": "eval:doc.purpose=='Material Issue'",
				"search_index": 1,
				"description": "Shop Supplies: build or repair job the supplies were used on.",
			},
			{
				"fieldname": "qc_work_order",
				"label": "TrulinX Work Order",
				"fieldtype": "Data",
				"insert_after": "qc_unit",
				"fetch_from": "qc_unit.trulinx_work_order",
				"read_only": 1,
				"depends_on": "eval:doc.qc_unit",
			},
		],
		"Material Request": [
			{
				"fieldname": "shop_supplies_reorder",
				"label": "Shop Supplies Reorder",
				"fieldtype": "Check",
				"insert_after": "material_request_type",
				"read_only": 1,
				"no_copy": 1,
				"description": "Draft built by Shop Supplies > Flag for Reorder. Later flags for the same warehouse are added to it.",
			},
		],
	}


def make_custom_fields():
	fields = get_custom_fields()
	for rows in fields.values():
		for row in rows:
			row["module"] = MODULE
	create_custom_fields(fields, update=True)


def after_install():
	make_custom_fields()


def after_migrate():
	make_custom_fields()


# ------------------------------------------------------------------ helpers
def _setting(field: str):
	return frappe.db.get_single_value(SETTINGS, field)


def _company(company: str | None = None) -> str:
	company = company or frappe.defaults.get_user_default("Company")
	if not company:
		companies = frappe.get_all("Company", pluck="name", limit=2)
		company = companies[0] if len(companies) == 1 else None
	if not company:
		frappe.throw(_("Select a Company."))
	return company


def _rows(items) -> list[dict]:
	if isinstance(items, str):
		items = json.loads(items or "[]")
	rows = [frappe._dict(r) for r in (items or []) if r and r.get("item_code")]
	if not rows:
		frappe.throw(_("Add at least one item."))
	return rows


def _check_item(item_code: str) -> frappe._dict:
	item = frappe.db.get_value(
		"Item",
		item_code,
		["name", "item_name", "stock_uom", "is_stock_item", "has_serial_no", "has_batch_no", "disabled"],
		as_dict=True,
	)
	if not item:
		frappe.throw(_("Item {0} does not exist.").format(item_code))
	if not item.is_stock_item or item.disabled:
		frappe.throw(_("Item {0} must be an enabled stock item.").format(item_code))
	if item.has_serial_no or item.has_batch_no:
		frappe.throw(
			_("Item {0} uses serial or batch numbers. Use the full Stock Entry form for it.").format(
				item_code
			)
		)
	return item


def _check_warehouse(warehouse: str, company: str):
	if not warehouse:
		frappe.throw(_("Select a Warehouse."))
	wh = frappe.db.get_value("Warehouse", warehouse, ["company", "is_group", "disabled"], as_dict=True)
	if not wh or wh.is_group or wh.disabled:
		frappe.throw(_("Warehouse {0} must be an enabled, non-group warehouse.").format(warehouse))
	if wh.company != company:
		frappe.throw(_("Warehouse {0} belongs to {1}, not {2}.").format(warehouse, wh.company, company))


def _posting(doc, posting_date: str | None):
	"""Back-dated entries need set_posting_time; future dates are not allowed."""
	if not posting_date or getdate(posting_date) == getdate(nowdate()):
		return
	if getdate(posting_date) > getdate(nowdate()):
		frappe.throw(_("Posting Date cannot be in the future."))
	doc.set_posting_time = 1
	doc.posting_date = posting_date


def current_rate(item_code: str, warehouse: str | None = None) -> float:
	"""Current unit cost: warehouse valuation rate, else item valuation rate, else last purchase rate."""
	rate = 0.0
	if warehouse:
		rate = flt(
			frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "valuation_rate")
		)
	if not rate:
		values = frappe.db.get_value(
			"Item", item_code, ["valuation_rate", "last_purchase_rate"], as_dict=True
		)
		if values:
			rate = flt(values.valuation_rate) or flt(values.last_purchase_rate)
	return rate


def on_hand(item_code: str, warehouse: str) -> float:
	return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"))


def receipt_row(row, warehouse: str) -> dict:
	"""Material Receipt row. A blank or zero cost uses the current rate; if there is none, zero valuation is allowed."""
	if flt(row.qty) <= 0:
		frappe.throw(_("Quantity for {0} must be above zero.").format(row.item_code))
	rate = flt(row.get("rate")) or current_rate(row.item_code, warehouse)
	values = {"item_code": row.item_code, "qty": flt(row.qty), "t_warehouse": warehouse, "basic_rate": rate}
	if rate <= 0:
		values["allow_zero_valuation_rate"] = 1
	return values


# ------------------------------------------------------------------ API
@frappe.whitelist()
def get_defaults() -> dict:
	return {
		"company": _company(),
		"warehouse": _setting("default_warehouse"),
		"item_group": _setting("default_item_group"),
		"stock_uom": frappe.db.get_single_value("Stock Settings", "stock_uom"),
		"posting_date": nowdate(),
	}


@frappe.whitelist()
def get_item_info(item_code: str, warehouse: str | None = None) -> dict:
	frappe.has_permission("Item", "read", throw=True)
	return {
		"rate": current_rate(item_code, warehouse),
		"on_hand": on_hand(item_code, warehouse) if warehouse else None,
		"stock_uom": frappe.db.get_value("Item", item_code, "stock_uom"),
		"reorder_qty": reorder_qty(item_code, warehouse),
	}


@frappe.whitelist(methods=["POST"])
def receive(
	warehouse: str,
	items: str | list,
	company: str | None = None,
	posting_date: str | None = None,
	note: str | None = None,
) -> str:
	company = _company(company)
	_check_warehouse(warehouse, company)
	rows = _rows(items)
	for row in rows:
		_check_item(row.item_code)
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt",
			"company": company,
			"to_warehouse": warehouse,
			"remarks": cstr(note).strip() or _("Shop Supplies: received"),
			"items": [receipt_row(r, warehouse) for r in rows],
		}
	)
	_posting(se, posting_date)
	se.insert()
	se.submit()
	return se.name


@frappe.whitelist(methods=["POST"])
def issue(
	warehouse: str,
	items: str | list,
	issued_to: str | None = None,
	qc_unit: str | None = None,
	note: str | None = None,
	company: str | None = None,
	posting_date: str | None = None,
) -> str:
	company = _company(company)
	_check_warehouse(warehouse, company)
	rows = _rows(items)
	expense_account = _setting("issue_expense_account")
	lines = []
	for row in rows:
		_check_item(row.item_code)
		if flt(row.qty) <= 0:
			frappe.throw(_("Quantity for {0} must be above zero.").format(row.item_code))
		line = {"item_code": row.item_code, "qty": flt(row.qty), "s_warehouse": warehouse}
		if expense_account:
			line["expense_account"] = expense_account
		lines.append(line)
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Issue",
			"purpose": "Material Issue",
			"company": company,
			"from_warehouse": warehouse,
			"issued_to": issued_to,
			"qc_unit": qc_unit,
			"remarks": cstr(note).strip() or _("Shop Supplies: issued"),
			"items": lines,
		}
	)
	_posting(se, posting_date)
	se.insert()
	se.submit()
	return se.name


@frappe.whitelist(methods=["POST"])
def count(
	warehouse: str,
	items: str | list,
	company: str | None = None,
	posting_date: str | None = None,
	note: str | None = None,
) -> str | None:
	"""Post counted quantities. Rows that match the system quantity are skipped."""
	company = _company(company)
	_check_warehouse(warehouse, company)
	rows = _rows(items)
	lines = []
	for row in rows:
		_check_item(row.item_code)
		if row.get("qty") in (None, "") or flt(row.qty) < 0:
			frappe.throw(_("Enter a counted quantity of zero or more for {0}.").format(row.item_code))
		if flt(row.qty) == on_hand(row.item_code, warehouse):
			continue
		rate = current_rate(row.item_code, warehouse)
		line = {
			"item_code": row.item_code,
			"warehouse": warehouse,
			"qty": flt(row.qty),
			"valuation_rate": rate,
		}
		if rate <= 0:
			line["allow_zero_valuation_rate"] = 1
		lines.append(line)
	if not lines:
		return None
	sr = frappe.get_doc(
		{
			"doctype": "Stock Reconciliation",
			"purpose": "Stock Reconciliation",
			"company": company,
			"items": lines,
		}
	)
	_posting(sr, posting_date)
	sr.insert()
	if cstr(note).strip():
		sr.add_comment("Comment", frappe.utils.escape_html(cstr(note).strip()))
	sr.submit()
	return sr.name


@frappe.whitelist(methods=["POST"])
def add_item(
	item_code: str,
	item_name: str,
	item_group: str,
	stock_uom: str,
	warehouse: str | None = None,
	reorder_level: float = 0,
	reorder_qty: float = 0,
	opening_qty: float = 0,
	unit_cost: float = 0,
	company: str | None = None,
) -> dict:
	"""Create a supply item (stock item) and optionally receive an opening quantity."""
	company = _company(company)
	item_code = cstr(item_code).strip()
	if not item_code or not cstr(item_name).strip() or not item_group or not stock_uom:
		frappe.throw(_("Enter the Item Code, Item Name, Item Group and UOM."))
	if frappe.db.exists("Item", item_code):
		frappe.throw(_("Item {0} already exists.").format(item_code))
	if warehouse:
		_check_warehouse(warehouse, company)
	if (flt(reorder_level) or flt(opening_qty)) and not warehouse:
		frappe.throw(_("Select a Warehouse for the reorder level or opening quantity."))
	item = frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": cstr(item_name).strip(),
			"item_group": item_group,
			"stock_uom": stock_uom,
			"is_stock_item": 1,
			"is_fixed_asset": 0,
			"include_item_in_manufacturing": 0,
			"item_defaults": [{"company": company, "default_warehouse": warehouse}] if warehouse else [],
		}
	)
	if flt(reorder_level) > 0:
		item.append(
			"reorder_levels",
			{
				"warehouse": warehouse,
				"warehouse_reorder_level": flt(reorder_level),
				"warehouse_reorder_qty": flt(reorder_qty) or flt(reorder_level),
				"material_request_type": "Purchase",
			},
		)
	item.insert()
	receipt = None
	if flt(opening_qty) > 0:
		receipt = receive(
			warehouse,
			[{"item_code": item.name, "qty": flt(opening_qty), "rate": flt(unit_cost)}],
			company=company,
			note=_("Shop Supplies: opening quantity"),
		)
	return {"item": item.name, "receipt": receipt}


# ------------------------------------------------------------------ barcodes
def ensure_item_barcode(doc, method=None):
	"""Item validate: give a stock item without barcodes one barcode equal to its item code.

	Skipped when another item already uses that value as a barcode."""
	if not doc.get("is_stock_item") or doc.get("is_fixed_asset") or doc.get("barcodes"):
		return
	code = cstr(doc.item_code or doc.name).strip()
	if not code:
		return
	if frappe.db.exists("Item Barcode", {"barcode": code, "parent": ["!=", doc.name]}):
		return
	doc.append("barcodes", {"barcode": code})


@frappe.whitelist()
def resolve_barcode(code: str, warehouse: str | None = None) -> dict:
	"""Find the stock item for a scanned or typed barcode (Item Barcode first, then Item Code)."""
	frappe.has_permission("Item", "read", throw=True)
	code = cstr(code).strip()
	if not code:
		frappe.throw(_("Scan or type a barcode."))
	item_code = frappe.db.get_value("Item Barcode", {"barcode": code, "parenttype": "Item"}, "parent")
	if not item_code and frappe.db.exists("Item", code):
		item_code = code
	if not item_code:
		frappe.throw(_("No item has barcode {0}.").format(escape_html(code)))
	item = _check_item(item_code)
	return {
		"item_code": item.name,
		"item_name": item.item_name,
		"stock_uom": item.stock_uom,
		"on_hand": on_hand(item.name, warehouse) if warehouse else None,
		"reorder_qty": reorder_qty(item.name, warehouse),
	}


def reorder_qty(item_code: str, warehouse: str | None) -> float:
	"""The item's reorder qty for the warehouse (Item Reorder), else 1."""
	if warehouse:
		qty = frappe.db.get_value(
			"Item Reorder",
			{"parent": item_code, "parenttype": "Item", "warehouse": warehouse},
			"warehouse_reorder_qty",
		)
		if flt(qty) > 0:
			return flt(qty)
	return 1.0


def _open_reorder_request(company: str, warehouse: str) -> str | None:
	return frappe.db.get_value(
		"Material Request",
		{
			"docstatus": 0,
			"material_request_type": "Purchase",
			"shop_supplies_reorder": 1,
			"company": company,
			"set_warehouse": warehouse,
		},
		"name",
		order_by="creation desc",
	)


@frappe.whitelist(methods=["POST"])
def flag_reorder(
	warehouse: str,
	items: str | list,
	schedule_date: str | None = None,
	company: str | None = None,
	note: str | None = None,
) -> dict:
	"""Add flagged items to the open draft Purchase Material Request for the warehouse, or start one.

	Items already on the draft are left as they are and reported back."""
	company = _company(company)
	_check_warehouse(warehouse, company)
	rows = _rows(items)
	schedule_date = schedule_date or nowdate()
	if getdate(schedule_date) < getdate(nowdate()):
		frappe.throw(_("Required By cannot be in the past."))
	name = _open_reorder_request(company, warehouse)
	if name:
		mr = frappe.get_doc("Material Request", name)
	else:
		mr = frappe.get_doc(
			{
				"doctype": "Material Request",
				"material_request_type": "Purchase",
				"company": company,
				"transaction_date": nowdate(),
				"schedule_date": schedule_date,
				"set_warehouse": warehouse,
				"shop_supplies_reorder": 1,
			}
		)
	existing = {r.item_code for r in mr.get("items", [])}
	added, skipped = [], []
	for row in rows:
		_check_item(row.item_code)
		if row.item_code in existing:
			skipped.append(row.item_code)
			continue
		qty = flt(row.get("qty")) or reorder_qty(row.item_code, warehouse)
		mr.append(
			"items",
			{"item_code": row.item_code, "qty": qty, "warehouse": warehouse, "schedule_date": schedule_date},
		)
		existing.add(row.item_code)
		added.append(row.item_code)
	if added:
		mr.save()
		if cstr(note).strip():
			mr.add_comment("Comment", escape_html(cstr(note).strip()))
	return {"material_request": mr.name if added or name else None, "added": added, "skipped": skipped}


# ------------------------------------------------------------------ labels
def qr_svg_data_uri(value: str) -> str:
	"""QR code as a crisp, scalable SVG data URI (works in wkhtmltopdf)."""
	import pyqrcode

	matrix = pyqrcode.create(cstr(value), error="M").code
	size = len(matrix)
	quiet = 2
	rects = "".join(
		f'<rect x="{x + quiet}" y="{y + quiet}" width="1" height="1"/>'
		for y, line in enumerate(matrix)
		for x, cell in enumerate(line)
		if cell
	)
	full = size + 2 * quiet
	svg = (
		f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {full} {full}" '
		f'shape-rendering="crispEdges"><rect width="{full}" height="{full}" fill="#fff"/>'
		f'<g fill="#000">{rects}</g></svg>'
	)
	return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def label_barcode(item_code: str) -> str:
	"""The value printed on the label: the item's first barcode, else its item code."""
	return (
		frappe.db.get_value(
			"Item Barcode", {"parent": item_code, "parenttype": "Item"}, "barcode", order_by="idx asc"
		)
		or item_code
	)


def get_supply_label_data(item_code: str) -> dict:
	"""Jinja helper for the Supply Label 2x4 print format."""
	value = label_barcode(item_code)
	return {"barcode": value, "qr": qr_svg_data_uri(value)}
