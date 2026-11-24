# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

"""QM-144 Request for Deviation (RFD) on a QC Unit.

The Deviation (QM-144) tab holds the unit's RFD. When the unit is saved the RFD:
- fills its blanks from the unit (project name and number, dates) and numbers itself RFD-YY-NNN,
- totals the cost breakdown,
- writes or updates its row in the unit's Change Orders table, so approval, re-inspection and the
  drawing revision follow the normal change order rules (QC Unit.validate_change_orders).

Called from QC Unit.validate, before validate_change_orders.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, fmt_money, getdate, today

from hse.shop_qc import change_control

PENDING = "Pending"
CUSTOMER = "Customer"
# Rows of the QM-144 Cost Breakdown table, loaded once when the RFD is started.
COST_CATEGORIES = (
	"Design Services",
	"Engineering Services",
	"Fabrication Costs",
	"Materials",
	"Equipment",
	"Subcontractor Costs",
	"Other Costs",
)
# Any of these filled in means the unit has an RFD.
RFD_FIELDS = ("rfd_number", "rfd_to", "rfd_from", "rfd_description", "rfd_reason", "rfd_impact")


def validate_unit(doc):
	if not is_started(doc):
		return
	doc.rfd_project_name = cstr(doc.rfd_project_name).strip() or doc.project_name or doc.model
	doc.rfd_project_number = cstr(doc.rfd_project_number).strip() or doc.trulinx_work_order or doc.rga_number
	doc.rfd_date_issued = doc.rfd_date_issued or today()
	doc.rfd_date = doc.rfd_date or doc.rfd_date_issued
	set_rfd_number(doc)
	set_cost_lines(doc)
	sync_change_order(doc)


def is_started(doc) -> bool:
	return any(cstr(doc.get(f)).strip() for f in RFD_FIELDS)


def set_rfd_number(doc):
	number = cstr(doc.rfd_number).strip().upper().replace(" ", "")
	if not number:
		number = next_rfd_number(doc.rfd_date_issued)
		frappe.msgprint(_("RFD Number {0} assigned.").format(frappe.bold(number)), alert=True)
	other = frappe.db.get_value("QC Unit", {"rfd_number": number, "name": ("!=", doc.name or "")}, "name")
	if other:
		frappe.throw(_("RFD Number {0} is already used on QC Unit {1}.").format(number, other))
	doc.rfd_number = number


def next_rfd_number(issued) -> str:
	"""Next RFD-YY-NNN for the year issued, after those on units and in change order rows."""
	prefix = "RFD-{0}-".format(getdate(issued or today()).strftime("%y"))
	used = frappe.get_all("QC Unit", filters={"rfd_number": ("like", prefix + "%")}, pluck="rfd_number")
	used += frappe.get_all(
		"QC Change Order",
		filters={"parenttype": "QC Unit", "co_no": ("like", prefix + "%")},
		pluck="co_no",
	)
	last = max((cint(u[len(prefix) :]) for u in used if cstr(u)[len(prefix) :].isdigit()), default=0)
	return f"{prefix}{last + 1:03d}"


def set_cost_lines(doc):
	if not cint(doc.rfd_cost_loaded) and not doc.get("rfd_cost_lines"):
		for category in COST_CATEGORIES:
			doc.append("rfd_cost_lines", {"description": category})
	doc.rfd_cost_loaded = 1
	total = 0
	for r in doc.get("rfd_cost_lines"):
		if flt(r.qty) < 0 or flt(r.unit_price) < 0:
			frappe.throw(
				_("Cost Breakdown row {0}: quantity and unit price cannot be negative.").format(r.idx)
			)
		if flt(r.qty) and flt(r.unit_price):
			r.amount = flt(flt(r.qty) * flt(r.unit_price), r.precision("amount"))
		total += flt(r.amount)
	doc.rfd_total_cost = total


def find_change_order(doc, co_no):
	key = cstr(co_no).strip().upper()
	if not key:
		return None
	return next((r for r in doc.get("change_orders") if cstr(r.co_no).strip().upper() == key), None)


def change_order_values(doc) -> dict:
	customer = doc.rfd_source == CUSTOMER
	notes = [_("From QM-144 Request for Deviation {0}.").format(doc.rfd_number)]
	if cstr(doc.rfd_reason).strip():
		notes.append(_("Reason: {0}").format(cstr(doc.rfd_reason).strip()))
	if cstr(doc.rfd_impact).strip():
		notes.append(_("Impact: {0}").format(cstr(doc.rfd_impact).strip()))
	if flt(doc.rfd_total_cost):
		currency = (
			frappe.get_cached_value("Company", doc.company, "default_currency") if doc.company else None
		)
		notes.append(_("Change order cost: {0}").format(fmt_money(doc.rfd_total_cost, currency=currency)))
	if cstr(doc.rfd_payment_schedule).strip():
		notes.append(_("Payment schedule: {0}").format(cstr(doc.rfd_payment_schedule).strip()))
	return {
		"co_no": doc.rfd_number,
		"co_date": getdate(doc.rfd_date_issued),
		"source": doc.rfd_source,
		# Customer request: their contact is who the RFD goes To; otherwise whoever it is From.
		"requested_by": (doc.rfd_to if customer else doc.rfd_from) or doc.rfd_from or doc.rfd_to,
		"customer_reference": doc.customer_po if customer else None,
		"description": cstr(doc.rfd_description).strip(),
		"notes": "\n".join(notes),
	}


def sync_change_order(doc):
	"""Pre-fill the unit's Change Orders row for this RFD. A Pending row is kept up to date;
	an approved, rejected or cancelled row is left alone."""
	if not cstr(doc.rfd_description).strip() or not doc.rfd_source:
		return  # Change orders need a description and a source; the form asks for both.
	row = find_change_order(doc, doc.rfd_number)
	if not row and doc.rfd_change_order:
		# RFD number corrected: carry the pending row over. A decided row stays with the old RFD.
		previous = find_change_order(doc, doc.rfd_change_order)
		if previous and previous.status == PENDING:
			row = previous
	values = change_order_values(doc)
	if not row:
		row = doc.append(
			"change_orders",
			{"status": PENDING, "change_type": change_control.default_change_type(doc.rfd_source), **values},
		)
		frappe.msgprint(
			_(
				"Change order {0} added from the RFD. Set its affected stages on the Construction Requirements tab."
			).format(frappe.bold(doc.rfd_number)),
			alert=True,
		)
	elif row.status == PENDING:
		row.update(values)
	elif any(
		(getdate(row.get(k)) if k == "co_date" and row.get(k) else cstr(row.get(k)))
		!= (v if k == "co_date" else cstr(v))
		for k, v in values.items()
	):
		frappe.msgprint(
			_(
				"Change order {0} is {1}, so the RFD changes were not copied to it. Set it back to Pending to update it."
			).format(frappe.bold(row.co_no), _(row.status)),
			indicator="orange",
			alert=True,
		)
	doc.rfd_change_order = row.co_no
