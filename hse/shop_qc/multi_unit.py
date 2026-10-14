# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Orders with more than one unit.

A work order (or RGA) with a quantity over 1 gets one QC Unit per physical unit, named
<work order>-<unit no>, e.g. 12345-1, 12345-2, 12345-3 (repairs: RGA-1973-1 ...). Quantity 1 or
blank keeps the plain work order name. Each unit has its own serial number, inspections,
NCRs and certificate; Create Remaining Units copies the shared order data from one unit
to the units not yet created.
"""

import frappe
from frappe import _
from frappe.utils import cint

REPAIR = "Repair"

# Belong to one physical unit: never copied to the other units of the order.
PER_UNIT_FIELDS = (
	"serial_no",
	"as_received_photo",
	"as_received_condition",
	"failure_analysis",
	"failure_cause",
	"condition_evaluation",
	"repair_recommendation",
	"warranty_status",
	"disposition",
	"work_performed",
	"additional_information",
	"technician",
	"evaluation_date",
	"start_date",
	"labor_inspection_hr",
	"labor_repair_hr",
	"labor_assembly_hr",
	"labor_testing_hr",
	"review_date",
	"reviewed_by",
	"released_by",
	"released_on",
	"qc_flag",
	"open_non_conformances",
	"sync_note",
)
PER_UNIT_TABLES = ("repair_parts", "accessory_items", "post_shipment_reviews")


def unit_base(doc) -> str | None:
	"""Name of the order: the work order for builds, RGA-<n> for repairs."""
	if doc.get("job_type") == REPAIR:
		rga = doc.get("rga_number")
		if not rga:
			return None
		return rga if rga.startswith("RGA") else f"RGA-{rga}"
	return doc.get("trulinx_work_order")


def unit_name(base: str, unit_no: int, qty: int) -> str:
	return f"{base}-{cint(unit_no)}" if cint(qty) > 1 else base


def group_filters(doc) -> dict:
	"""Every QC Unit of the same order."""
	if doc.get("job_type") == REPAIR:
		return {"job_type": REPAIR, "rga_number": doc.get("rga_number")}
	return {"job_type": ("!=", REPAIR), "trulinx_work_order": doc.get("trulinx_work_order")}


def validate_unit_numbers(doc) -> None:
	qty, no = cint(doc.get("unit_qty")), cint(doc.get("unit_no"))
	if qty < 0 or no < 0:
		frappe.throw(_("Unit No. and Order Quantity cannot be negative."))
	if qty > 1 and not no:
		frappe.throw(_("Enter the Unit No. (1 to {0}) for an order of {0} units.").format(qty))
	if qty and no > qty:
		frappe.throw(_("Unit No. {0} is more than the Order Quantity of {1}.").format(no, qty))
	if no and (doc.get("trulinx_work_order") or doc.get("rga_number")):
		other = frappe.db.get_value(
			"QC Unit", {**group_filters(doc), "unit_no": no, "name": ("!=", doc.name or "")}, "name"
		)
		if other:
			frappe.throw(_("Unit No. {0} of this order is already QC Unit {1}.").format(no, other))


def get_order_units(doc) -> list[frappe._dict]:
	return frappe.get_all(
		"QC Unit",
		filters=group_filters(doc),
		fields=["name", "unit_no", "unit_qty", "status"],
		order_by="unit_no asc, creation asc",
	)


def ensure_numbered_name(doc):
	"""A unit saved before its quantity went over 1 still has the plain order name: rename it."""
	base = unit_base(doc)
	if not base or cint(doc.unit_qty) <= 1:
		return doc
	if not cint(doc.unit_no):
		frappe.throw(_("Enter the Unit No. on {0} first.").format(doc.name))
	new = unit_name(base, doc.unit_no, doc.unit_qty)
	if doc.name != new:
		if frappe.db.exists("QC Unit", new):
			frappe.throw(_("Cannot rename {0} to {1}: that QC Unit already exists.").format(doc.name, new))
		frappe.rename_doc("QC Unit", doc.name, new, force=True, show_alert=False)
		doc = frappe.get_doc("QC Unit", new)
	return doc


def copy_unit(source, unit_no: int, qty: int | None = None):
	"""A new QC Unit for another unit of the same order, with the shared order data."""
	new = frappe.copy_doc(source)
	new.unit_no = unit_no
	if qty:
		new.unit_qty = qty
	new.status = "Pending Build"
	for field in PER_UNIT_FIELDS:
		new.set(field, None)
	for table in PER_UNIT_TABLES:
		new.set(table, [])
	new.print_photos = source.print_photos
	# same order data as the source, so the next TrulinX sync sees it unchanged
	new.sync_hash = source.sync_hash
	new.flags.from_trulinx_sync = source.flags.get("from_trulinx_sync")
	new.insert()
	return new


def make_missing_units(doc) -> list[str]:
	"""Create every unit 1..Order Quantity that does not exist yet, copying from doc."""
	qty = cint(doc.unit_qty)
	if qty <= 1:
		frappe.throw(_("Set the Order Quantity above 1 first."))
	doc = ensure_numbered_name(doc)
	existing = {cint(u.unit_no) for u in get_order_units(doc)}
	created = []
	for n in range(1, qty + 1):
		if n not in existing:
			created.append(copy_unit(doc, n, qty).name)
	# keep the order quantity the same on every unit
	for u in get_order_units(doc):
		if cint(u.unit_no) <= qty and cint(u.unit_qty) != qty:
			frappe.db.set_value("QC Unit", u.name, "unit_qty", qty)
	return created


@frappe.whitelist(methods=["POST"])
def create_remaining_units(qc_unit: str) -> dict:
	frappe.has_permission("QC Unit", "create", throw=True)
	doc = frappe.get_doc("QC Unit", qc_unit)
	doc.check_permission("write")
	if doc.status == "Cancelled":
		frappe.throw(_("Cannot copy from a cancelled unit."))
	created = make_missing_units(doc)
	renamed_to = frappe.db.get_value("QC Unit", {**group_filters(doc), "unit_no": doc.unit_no}, "name")
	return {"renamed_to": renamed_to, "created": created}


@frappe.whitelist()
def get_order_status(qc_unit: str) -> dict:
	doc = frappe.get_doc("QC Unit", qc_unit)
	doc.check_permission("read")
	units = get_order_units(doc)
	return {"qty": cint(doc.unit_qty), "units": units, "missing": max(cint(doc.unit_qty) - len(units), 0)}
