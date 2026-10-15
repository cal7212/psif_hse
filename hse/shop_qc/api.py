# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""TrulinX -> Frappe sync for QC Unit.

Endpoint:  POST /api/method/hse.shop_qc.api.upsert_qc_units
           (the old path hse.hpu_build.api.upsert_hpu_units still works)
Auth:      token <api_key>:<api_secret> of a dedicated user with the "HPU Sync" role
Body:      {"units": [{"work_order": "...", "model": "...", ...}, ...]}   (max 500 per call)
"""

import hashlib
import json

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, getdate, now_datetime, sbool

from hse.shop_qc.doctype.qc_unit.qc_unit import normalise_wo

MAX_BATCH = 500

# TrulinX/export column -> QC Unit field. Only these fields can be written by the sync.
# QC fields (status, released_*, open_non_conformances) are deliberately absent.
FIELD_MAP = {
	"work_order": "trulinx_work_order",
	"line": "trulinx_line",
	"sales_order": "trulinx_sales_order",
	"customer_po": "customer_po",
	"wo_status": "trulinx_status",
	"trulinx_url": "trulinx_url",
	"customer_name": "customer_name",
	"wo_date": "wo_date",
	"promised_date": "promised_date",
	"ship_date": "trulinx_ship_date",
	"model": "model",
	"description": "description",
	"serial_no": "serial_no",
	"motor_hp": "motor_hp",
	"voltage": "voltage",
	"phase": "phase",
	"hz": "hz",
	"pump_type": "pump_type",
	"flow_gpm": "flow_gpm",
	"relief_setting_psi": "relief_setting_psi",
	"max_operating_psi": "max_operating_psi",
	"reservoir_gal": "reservoir_gal",
	"fluid": "fluid",
	"target_cleanliness": "target_cleanliness",
	"drawing_rev": "drawing_rev",
	"shop": "shop",
	"product_type": "product_type",
	"quantity": "unit_qty",
}
DEFAULT_SHOP = "HPU"  # work orders without a shop column are HPU builds
DEFAULT_PRODUCT_TYPE = "Power Unit"
DATE_FIELDS = {"wo_date", "promised_date", "trulinx_ship_date"}
FLOAT_FIELDS = {"motor_hp", "flow_gpm", "relief_setting_psi", "max_operating_psi", "reservoir_gal"}
INT_FIELDS = {"unit_qty"}

# Map raw TrulinX WO status text -> sync action. Confirm the real values with Tribute/your admin.
CANCELLED_STATUSES = {"CANCELLED", "CANCELED", "VOID", "DELETED"}
SHIPPED_STATUSES = {"SHIPPED", "INVOICED", "CLOSED"}


@frappe.whitelist(methods=["POST"])
def upsert_qc_units(units: list | str, company: str | None = None, dry_run: bool = False) -> dict:
	if not (frappe.has_permission("QC Unit", "create") and frappe.has_permission("QC Unit", "write")):
		frappe.throw(_("Not permitted to sync QC Units"), frappe.PermissionError)

	dry_run = sbool(dry_run)
	if isinstance(units, str):
		units = json.loads(units)
	if len(units) > MAX_BATCH:
		frappe.throw(_("Send at most {0} units per call").format(MAX_BATCH))

	company = (
		company
		or frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
	)
	result = {"created": [], "updated": [], "unchanged": [], "errors": []}

	for row in units:
		wo = normalise_wo(row.get("work_order"))
		if not wo:
			result["errors"].append({"work_order": None, "error": "Missing work_order"})
			continue
		frappe.db.savepoint("qc_row")
		try:
			outcome = _upsert_one(wo, row, company, dry_run)
			result[outcome].append(wo)
		except Exception as e:
			frappe.db.rollback(save_point="qc_row")
			result["errors"].append({"work_order": wo, "error": cstr(e)[:500]})
			frappe.log_error(title=f"QC Unit sync failed: {wo}", message=frappe.get_traceback())

	if dry_run:
		frappe.db.rollback()
	return result


def _upsert_one(wo: str, row: dict, company: str, dry_run: bool) -> str:
	"""Create or update every QC Unit of a work order.

	A quantity over 1 means one QC Unit per unit (WO-1, WO-2 ...). Order data goes to all of
	them; a serial number is only taken when the order is a single unit."""
	values = _clean(row)
	values["trulinx_work_order"] = wo
	row_hash = hashlib.sha1(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()

	# Match on the work order field, not the record name: repairs are named by RGA number,
	# and multi-unit orders by WO-<unit no>.
	units = frappe.get_all(
		"QC Unit",
		filters={"trulinx_work_order": wo, "parent_qc_unit": ("is", "not set")},
		fields=["name", "unit_no", "unit_qty", "sync_hash"],
		order_by="unit_no asc, creation asc",
	)
	qty = cint(values.get("unit_qty")) or max(len(units), 1)
	if units and len(units) >= qty and all(u.sync_hash == row_hash for u in units):
		for u in units:
			frappe.db.set_value("QC Unit", u.name, "last_synced_on", now_datetime(), update_modified=False)
		return "unchanged"

	shared = {k: v for k, v in values.items() if v not in (None, "")}
	if qty > 1 or len(units) > 1:
		shared.pop("serial_no", None)

	if not units:
		doc = frappe.new_doc("QC Unit")
		doc.company = company
		doc.status = "Pending Build"
		doc.job_type = "New Build"
		doc.shop = DEFAULT_SHOP
		doc.product_type = DEFAULT_PRODUCT_TYPE
		if qty > 1:
			doc.unit_no = 1
		_save_synced(doc, shared, values, row_hash, created=True)
		if qty > 1:
			_make_missing(doc.name)
		return "created"

	for u in units:
		doc = frappe.get_doc("QC Unit", u.name)
		update = dict(shared)
		if cint(u.unit_no) > qty:
			# TrulinX quantity went down: keep the unit and its records, flag it for review.
			update.pop("unit_qty", None)
			doc.qc_flag = _(
				"TrulinX now shows {0} unit(s) on work order {1}; this is unit {2}. Cancel it if it is no longer being built."
			).format(qty, wo, u.unit_no)
		elif qty > 1 and not cint(doc.unit_no):
			doc.unit_no = 1
		_save_synced(doc, update, values, row_hash, created=False)
	if qty > len([u for u in units if cint(u.unit_no) <= qty]):
		_make_missing(units[0].name)
	return "updated"


def _save_synced(doc, update: dict, values: dict, row_hash: str, created: bool) -> None:
	# Never blank out data already in Frappe because TrulinX sent an empty column.
	doc.update(update)
	if values.get("customer_name") and not doc.customer:
		doc.customer = frappe.db.get_value("Customer", {"customer_name": values["customer_name"]}, "name")
	_apply_trulinx_status(doc)
	doc.sync_source = "TrulinX"
	doc.sync_hash = row_hash
	doc.last_synced_on = now_datetime()
	doc.sync_note = "Created from TrulinX" if created else "Updated from TrulinX"
	doc.flags.from_trulinx_sync = True
	doc.save()


def _make_missing(name: str) -> None:
	from hse.shop_qc.multi_unit import make_missing_units

	doc = frappe.get_doc("QC Unit", name)
	doc.flags.from_trulinx_sync = True
	make_missing_units(doc)


def _clean(row: dict) -> dict:
	out = {}
	for src, field in FIELD_MAP.items():
		if src not in row:
			continue
		val = row.get(src)
		if isinstance(val, str):
			val = val.strip()
		if val in (None, ""):
			out[field] = None
		elif field in DATE_FIELDS:
			out[field] = str(getdate(val))
		elif field in FLOAT_FIELDS:
			out[field] = flt(val)
		elif field in INT_FIELDS:
			out[field] = cint(val)
		else:
			out[field] = cstr(val)
	return out


def _apply_trulinx_status(doc) -> None:
	"""TrulinX owns the order lifecycle; Frappe owns QC. Only flag conflicts, never 'release'."""
	trx = cstr(doc.trulinx_status).strip().upper()
	if trx in CANCELLED_STATUSES and doc.status not in ("Released", "Shipped"):
		doc.status = "Cancelled"
	elif trx in SHIPPED_STATUSES or doc.trulinx_ship_date:
		if doc.status == "Released":
			doc.status = "Shipped"
		elif doc.status != "Shipped":
			doc.qc_flag = _("TrulinX shows this unit shipped/invoiced but QC status is {0}.").format(
				doc.status
			)


# Backward-compatible name for the original endpoint
upsert_hpu_units = upsert_qc_units
