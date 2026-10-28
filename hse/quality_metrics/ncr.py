# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""QM-104 Non-Conformance Report (NCR) rules for the Nonconformance Report doctype.

Fills what can be derived from the originating QC unit or inspection, keeps the log numbers
unique, and enforces the form's closure rules.
"""

import frappe
from frappe import _
from frappe.utils import cstr, getdate, nowdate

NCR_PRINT_FORMAT = "QM-104 Non-Conformance Report"
OTHER = "Other"
CUSTOMER_APPROVAL = ("Use As-Is", "Repair")
DISPOSITIONS = (
	"Rework to Specification",
	"Use As-Is",
	"Scrap and Remake",
	"Repair",
	"Return to Supplier",
	OTHER,
)
SOURCES = (
	"Receiving Inspection",
	"In-Process Inspection",
	"Final Inspection",
	"Customer",
	"Supplier",
	"Internal Audit",
	"Asset Inspection",
	"Housekeeping Inspection",
	OTHER,
)


# ---------------------------------------------------------------- document events
def validate(doc, method=None):
	from hse.quality_metrics import rework

	fill_from_origin(doc)
	rework.validate(doc)
	validate_log_number(doc, "ncr_no", _("NCR No."))
	if doc.get("disposition") == OTHER and not cstr(doc.get("disposition_other")).strip():
		frappe.throw(_("Describe the Other disposition."))
	if doc.get("reject_qty") and doc.get("lot_qty") and doc.reject_qty > doc.lot_qty:
		frappe.throw(_("Reject Quantity cannot be more than Lot Quantity."))
	if (
		doc.get("approved_date")
		and doc.get("ncr_date")
		and getdate(doc.approved_date) < getdate(doc.ncr_date)
	):
		frappe.throw(_("Approved Date cannot be before the NCR Date."))
	if doc.status == "Resolved" and (doc.is_new() or doc.has_value_changed("status")):
		validate_closure(doc)


def validate_closure(doc) -> None:
	"""QM-104: disposition authorized, customer approval where required, and QA accepts the correction."""
	missing = []
	if not doc.get("disposition"):
		missing.append(_("Disposition"))
	if doc.get("disposition") in CUSTOMER_APPROVAL and not cstr(doc.get("auth_customer")).strip():
		missing.append(_("Customer (approval required for {0})").format(_(doc.disposition)))
	if doc.get("quality_verification") != "Accept":
		missing.append(_("Quality Verification: Accept"))
	if missing:
		frappe.throw(
			_("Cannot resolve this {0} until these are completed: {1}").format(
				_("Rework") if doc.get("record_type") == "Rework" else _("NCR"), ", ".join(missing)
			),
			title=_("Resolution Blocked"),
		)


def fill_from_origin(doc) -> None:
	"""Fill blank header fields from the QC unit or inspection that raised the NCR."""
	if not doc.get("ncr_date"):
		doc.ncr_date = getdate(doc.creation) if doc.get("creation") else nowdate()
	if not doc.get("initiator"):
		doc.initiator = doc.owner or frappe.session.user
	if doc.get("initiator") and not doc.get("initiator_name"):
		doc.initiator_name = frappe.db.get_value("User", doc.initiator, "full_name")
	if not doc.get("source"):
		doc.source = guess_source(doc)
	if doc.get("qc_unit"):
		unit = frappe.db.get_value(
			"QC Unit",
			doc.qc_unit,
			[
				"job_type",
				"rga_number",
				"trulinx_work_order",
				"trulinx_sales_order",
				"customer_po",
				"drawing_rev",
				"unit_qty",
			],
			as_dict=True,
		)
		if unit:
			if not doc.get("job_no"):
				doc.job_no = (unit.trulinx_work_order if unit.job_type != "Repair" else None) or doc.qc_unit
			if not doc.get("contract"):
				doc.contract = unit.customer_po or unit.trulinx_sales_order
			if not doc.get("drawing_no"):
				doc.drawing_no = unit.drawing_rev
			if not doc.get("lot_qty") and unit.unit_qty:
				doc.lot_qty = unit.unit_qty


def guess_source(doc) -> str | None:
	if doc.get("qc_inspection"):
		stage = frappe.db.get_value("QC Inspection", doc.qc_inspection, "stage")
		final = stage and frappe.db.get_value("QC Stage", stage, "is_final_release")
		return "Final Inspection" if final else "In-Process Inspection"
	if doc.get("asset_inspection"):
		return "Asset Inspection"
	if doc.get("housekeeping_inspection"):
		return "Housekeeping Inspection"
	return None


def validate_log_number(doc, fieldname: str, label: str) -> None:
	"""Log numbers are typed in from the internal log: trim them and keep them unique."""
	value = cstr(doc.get(fieldname)).strip() or None
	doc.set(fieldname, value)
	if not value:
		return
	other = frappe.db.get_value("Nonconformance Report", {fieldname: value, "name": ("!=", doc.name)}, "name")
	if other:
		frappe.throw(_("{0} {1} is already used on {2}.").format(label, value, other))


# Source records that point back to the NCR that they raised. Each NCR also points to its
# source, so without this neither could be deleted.
NCR_SOURCE_LINKS = (
	("QC Inspection", "non_conformance"),
	("QC Hose Test", "non_conformance"),  # child of QC Inspection; docstatus follows the parent
	("Asset Inspection", "non_conformance"),
	("Housekeeping Inspection", "non_conformance"),
	("QC Missing Part", "non_conformance"),  # rows on a QC Unit, and the copies on its checks
)


def on_trash(doc, method=None):
	"""Deleting an NCR (e.g. test data) clears the link back to it on draft or cancelled source
	records. A submitted source keeps its NCR: cancel it first. Runs before the link check."""
	submitted, to_clear = [], []
	for doctype, field in NCR_SOURCE_LINKS:
		if not frappe.db.has_column(doctype, field):
			continue
		for row in frappe.get_all(doctype, filters={field: doc.name}, fields=["name", "docstatus"]):
			if row.docstatus == 1:
				submitted.append(f"{_(doctype)} {row.name}")
			else:
				to_clear.append((doctype, row.name, field))
	if submitted:
		frappe.throw(
			_("Cancel these submitted records first; they raised NCR {0}: {1}").format(
				frappe.bold(doc.name), ", ".join(submitted)
			),
			title=_("Linked Submitted Records"),
		)
	for doctype, name, field in to_clear:
		frappe.db.set_value(doctype, name, field, None, update_modified=False)


def block_legacy_insert(doc, method=None):
	"""ERPNext's Non Conformance is an archive now; NCRs and Rework are Nonconformance Reports."""
	if frappe.flags.in_install or frappe.flags.in_migrate:
		return
	frappe.throw(
		_("New NCRs and Rework records are created as a Nonconformance Report."),
		title=_("Use Nonconformance Report"),
	)
