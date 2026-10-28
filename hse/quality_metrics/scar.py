# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""QM-134 Supplier Corrective Action Report (SCAR) on the Nonconformance Report doctype.

A SCAR tab on NCR and Rework records holds the QM-134 fields. Ticking SCAR Required needs the
SCAR Number from the internal SCAR log and the supplier, stamps the issue date, and fills blanks
from the NCR or Rework. Rejecting the supplier's corrective action needs a reason, and approving
it needs the supplier's root cause, containment and corrective action.
"""

import frappe
from frappe import _
from frappe.utils import cstr, getdate, nowdate

from hse.quality_metrics.capa import is_blank

SCAR_PRINT_FORMAT = "QM-134 SCAR Report"
ISSUED, RESPONSE_RECEIVED, REJECTED, APPROVED, CANCELLED = (
	"Issued",
	"Response Received",
	"Rejected",
	"Approved",
	"Cancelled",
)
SCAR_STATUSES = (ISSUED, RESPONSE_RECEIVED, REJECTED, APPROVED, CANCELLED)

# SCAR field -> (NCR field, Rework field) it starts from when blank.
FILL_FROM = {
	"scar_qty_received": ("lot_qty", "rw_lot_qty"),
	"scar_qty_rejected": ("reject_qty", "rw_reject_qty"),
	"scar_drawing_rev": ("drawing_no", "rw_drawing_no"),
	"scar_discrepancy": ("details", "rw_requirement"),
}


def validate(doc, method=None):
	if not doc.get("scar_required"):
		return
	start_scar(doc)
	fill_from_ncr(doc)
	validate_scar(doc)


def start_scar(doc) -> None:
	from hse.quality_metrics.ncr import validate_log_number

	validate_log_number(doc, "scar_no", _("SCAR Number"))
	if not doc.get("scar_no"):
		frappe.throw(_("Enter the SCAR Number from the internal SCAR log."), title=_("SCAR Number Required"))
	if doc.get("scar_supplier") and not cstr(doc.get("scar_supplier_name")).strip():
		doc.scar_supplier_name = frappe.db.get_value("Supplier", doc.scar_supplier, "supplier_name")
	if not cstr(doc.get("scar_supplier_name")).strip():
		frappe.throw(_("Select the Supplier or enter the Supplier Name."), title=_("Supplier Required"))
	if not doc.get("scar_status"):
		doc.scar_status = ISSUED
	if not doc.get("scar_issued_date"):
		doc.scar_issued_date = nowdate()


def fill_from_ncr(doc) -> None:
	"""Blank SCAR fields start from what the NCR or Rework already records."""
	rework = doc.get("record_type") == "Rework"
	for target, (ncr_field, rework_field) in FILL_FROM.items():
		source = rework_field if rework else ncr_field
		value = doc.get(source) or doc.get(ncr_field)
		if is_blank(doc.get(target)) and not is_blank(value):
			doc.set(target, value)
	if not doc.get("scar_part_description") and doc.get("capa_part_description"):
		doc.scar_part_description = doc.capa_part_description


def validate_scar(doc) -> None:
	if doc.get("scar_qty_rejected") and doc.get("scar_qty_received"):
		if doc.scar_qty_rejected > doc.scar_qty_received:
			frappe.throw(_("Qty Rejected cannot be more than Qty Received."))
	issued = getdate(doc.scar_issued_date) if doc.get("scar_issued_date") else None
	for field, label in (
		("scar_response_due", _("Date Supplier Response Required")),
		("scar_response_received", _("Response Received On")),
		("scar_rejected_date", _("Rejected Date")),
		("scar_approved_date", _("Approved Date")),
	):
		if issued and doc.get(field) and getdate(doc.get(field)) < issued:
			frappe.throw(_("{0} cannot be before the Date SCAR Issued.").format(label))

	status = doc.get("scar_status")
	if status == RESPONSE_RECEIVED and not doc.get("scar_response_received"):
		doc.scar_response_received = nowdate()
	if status == REJECTED:
		if not doc.get("scar_rejected_date"):
			doc.scar_rejected_date = nowdate()
		missing = []
		if not cstr(doc.get("scar_rejection_reason")).strip():
			missing.append(_("Reason Corrective Action Rejected"))
		if not doc.get("scar_rejected_by"):
			missing.append(_("Corrective Action Rejected By"))
		if missing:
			frappe.throw(
				_("Cannot reject this SCAR until these are completed: {0}").format(", ".join(missing)),
				title=_("SCAR Rejection Blocked"),
			)
	if status == APPROVED and (doc.is_new() or doc.has_value_changed("scar_status")):
		validate_approval(doc)


def validate_approval(doc) -> None:
	if not doc.get("scar_approved_date"):
		doc.scar_approved_date = nowdate()
	if not doc.get("scar_response_received"):
		doc.scar_response_received = doc.scar_approved_date
	missing = []
	if is_blank(doc.get("scar_root_cause")):
		missing.append(_("Root Cause"))
	if not doc.get("scar_containment"):
		missing.append(_("Containment"))
	if is_blank(doc.get("scar_corrective_action")):
		missing.append(_("Corrective Action"))
	if not doc.get("scar_approved_by"):
		missing.append(_("Corrective Action Approved By"))
	if missing:
		frappe.throw(
			_("Cannot approve this SCAR until these are completed: {0}").format(", ".join(missing)),
			title=_("SCAR Approval Blocked"),
		)
