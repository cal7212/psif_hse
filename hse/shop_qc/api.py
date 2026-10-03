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
from frappe.utils import cstr, flt, getdate, now_datetime, sbool

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
}
DEFAULT_SHOP = "HPU"  # work orders without a shop column are HPU builds
DEFAULT_PRODUCT_TYPE = "Power Unit"
DATE_FIELDS = {"wo_date", "promised_date", "trulinx_ship_date"}
FLOAT_FIELDS = {"motor_hp", "flow_gpm", "relief_setting_psi", "max_operating_psi", "reservoir_gal"}

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
	values = _clean(row)
	values["trulinx_work_order"] = wo
	row_hash = hashlib.sha1(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()

	# Match on the work order field, not the record name: repairs are named by RGA number.
	name = frappe.db.get_value("QC Unit", {"trulinx_work_order": wo}, "name")
	if name and frappe.db.get_value("QC Unit", name, "sync_hash") == row_hash:
		frappe.db.set_value("QC Unit", name, "last_synced_on", now_datetime(), update_modified=False)
		return "unchanged"

	doc = frappe.get_doc("QC Unit", name) if name else frappe.new_doc("QC Unit")
	if not name:
		doc.company = company
		doc.status = "Pending Build"
		doc.job_type = "New Build"
		doc.shop = DEFAULT_SHOP
		doc.product_type = DEFAULT_PRODUCT_TYPE

	# Never blank out data already in Frappe because TrulinX sent an empty column.
	doc.update({k: v for k, v in values.items() if v not in (None, "")})

	if values.get("customer_name") and not doc.customer:
		doc.customer = frappe.db.get_value("Customer", {"customer_name": values["customer_name"]}, "name")

	_apply_trulinx_status(doc)

	doc.sync_source = "TrulinX"
	doc.sync_hash = row_hash
	doc.last_synced_on = now_datetime()
	doc.sync_note = "Created from TrulinX" if not name else "Updated from TrulinX"
	doc.flags.from_trulinx_sync = True
	doc.save()
	return "updated" if name else "created"


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
