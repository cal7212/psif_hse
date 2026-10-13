# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""QM-104 Non-Conformance Report (NCR) layout for the ERPNext Non Conformance doctype.

Adds the form's header block, cause, disposition, authorization and verification fields,
relabels the standard fields to the form's wording, fills what can be derived from the
originating QC unit or inspection, and enforces the form's closure rules.
"""

import frappe
from frappe import _
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
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
DISPOSITION_DEP = "eval:doc.disposition=='Other'"
CUSTOMER_DEP = "eval:['Use As-Is','Repair'].includes(doc.disposition)"

# Standard and earlier custom fields renamed to the form's wording
LABELS = {
	"details": "Deficiency Description",
	"corrective_action": "Correction",
	"verified_by": "Inspected By",
	"verification_date": "Inspected Date",
}


def get_custom_fields() -> list[dict]:
	return [
		# ----------------------------------------------------------- NCR header block
		{
			"fieldname": "ncr_section",
			"label": "NCR Information",
			"fieldtype": "Section Break",
			"insert_after": "resolved_on",
		},
		{
			"fieldname": "ncr_date",
			"label": "Date",
			"fieldtype": "Date",
			"default": "Today",
			"insert_after": "ncr_section",
			"in_list_view": 1,
		},
		{
			"fieldname": "initiator",
			"label": "Initiator",
			"fieldtype": "Link",
			"options": "User",
			"default": "__user",
			"insert_after": "ncr_date",
		},
		{
			"fieldname": "initiator_name",
			"label": "Initiator Name",
			"fieldtype": "Data",
			"fetch_from": "initiator.full_name",
			"read_only": 1,
			"insert_after": "initiator",
		},
		{
			"fieldname": "contract",
			"label": "Contract",
			"fieldtype": "Data",
			"insert_after": "initiator_name",
			"description": "Customer PO or contract; filled from the QC unit when blank.",
		},
		{
			"fieldname": "drawing_no",
			"label": "Drawing No.",
			"fieldtype": "Data",
			"insert_after": "contract",
		},
		{
			"fieldname": "source",
			"label": "Source",
			"fieldtype": "Select",
			"options": "\n" + "\n".join(SOURCES),
			"insert_after": "drawing_no",
			"in_standard_filter": 1,
		},
		{"fieldname": "ncr_column_break", "fieldtype": "Column Break", "insert_after": "source"},
		{
			"fieldname": "job_no",
			"label": "Job No.",
			"fieldtype": "Data",
			"insert_after": "ncr_column_break",
			"in_standard_filter": 1,
			"description": "TrulinX work order or RGA; filled from the QC unit when blank.",
		},
		{
			"fieldname": "lot_qty",
			"label": "Lot Quantity",
			"fieldtype": "Float",
			"insert_after": "job_no",
		},
		{
			"fieldname": "reject_qty",
			"label": "Reject Quantity",
			"fieldtype": "Float",
			"insert_after": "lot_qty",
		},
		# ----------------------------------------------------------- Cause
		{
			"fieldname": "cause",
			"label": "Cause",
			"fieldtype": "Text Editor",
			"insert_after": "details",
		},
		# ----------------------------------------------------------- Disposition
		{
			"fieldname": "ncr_disposition_section",
			"label": "Disposition",
			"fieldtype": "Section Break",
			"insert_after": "preventive_action",
			"description": "To be completed by management or QA.",
		},
		{
			"fieldname": "disposition",
			"label": "Disposition",
			"fieldtype": "Select",
			"options": "\n" + "\n".join(DISPOSITIONS),
			"insert_after": "ncr_disposition_section",
			"in_standard_filter": 1,
			"description": "Use As-Is and Repair require customer approval.",
		},
		{
			"fieldname": "disposition_other",
			"label": "Other Disposition",
			"fieldtype": "Data",
			"insert_after": "disposition",
			"depends_on": DISPOSITION_DEP,
			"mandatory_depends_on": DISPOSITION_DEP,
		},
		{
			"fieldname": "capa_scar_reference",
			"label": "CAPA / SCAR Document #",
			"fieldtype": "Data",
			"insert_after": "disposition_other",
			"description": "If CAPA or SCAR applies, record the document number.",
		},
		{
			"fieldname": "ncr_authorization_column",
			"label": "Authorization of Disposition",
			"fieldtype": "Column Break",
			"insert_after": "capa_scar_reference",
		},
		{
			"fieldname": "auth_project_manager",
			"label": "Project Manager",
			"fieldtype": "Link",
			"options": "Employee",
			"insert_after": "ncr_authorization_column",
		},
		{
			"fieldname": "auth_operations_manager",
			"label": "Operations Manager",
			"fieldtype": "Link",
			"options": "Employee",
			"insert_after": "auth_project_manager",
		},
		{
			"fieldname": "auth_quality_manager",
			"label": "Quality Manager",
			"fieldtype": "Link",
			"options": "Employee",
			"insert_after": "auth_operations_manager",
		},
		{
			"fieldname": "auth_customer",
			"label": "Customer",
			"fieldtype": "Data",
			"insert_after": "auth_quality_manager",
			"description": "Customer approver name or approval reference.",
			"mandatory_depends_on": CUSTOMER_DEP,
		},
		# ----------------------------------------------------------- Verification of correction
		{
			"fieldname": "ncr_verification_section",
			"label": "Verification of Correction",
			"fieldtype": "Section Break",
			"insert_after": "auth_customer",
		},
		{
			"fieldname": "quality_verification",
			"label": "Quality Verification",
			"fieldtype": "Select",
			"options": "\nAccept\nReject",
			"insert_after": "ncr_verification_section",
			"description": "Must be Accept to resolve.",
		},
		{
			"fieldname": "verification_comments",
			"label": "Comments",
			"fieldtype": "Small Text",
			"insert_after": "quality_verification",
		},
		{
			"fieldname": "ncr_verification_column",
			"fieldtype": "Column Break",
			"insert_after": "verification_comments",
		},
		# verified_by / verification_date (Inspected By / Date) are moved here below.
		{
			"fieldname": "approved_by",
			"label": "Approved By",
			"fieldtype": "Link",
			"options": "Employee",
			"insert_after": "verification_date",
		},
		{
			"fieldname": "approved_date",
			"label": "Approved Date",
			"fieldtype": "Date",
			"insert_after": "approved_by",
		},
	]


# The Asset Inspection module creates these; the NCR places them in Verification of Correction.
MOVED_FIELDS = {"verified_by": "ncr_verification_column", "verification_date": "verified_by"}


def setup_ncr(module: str) -> None:
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	rows = get_custom_fields()
	for row in rows:
		row["module"] = module
	create_custom_fields({"Non Conformance": rows}, update=True)
	for fieldname, after in MOVED_FIELDS.items():
		name = frappe.db.get_value("Custom Field", {"dt": "Non Conformance", "fieldname": fieldname})
		if name:
			frappe.db.set_value("Custom Field", name, "insert_after", after, update_modified=False)
	for fieldname, label in LABELS.items():
		if is_custom(fieldname):
			name = frappe.db.get_value("Custom Field", {"dt": "Non Conformance", "fieldname": fieldname})
			frappe.db.set_value("Custom Field", name, "label", label, update_modified=False)
		else:
			make_property_setter(
				"Non Conformance", fieldname, "label", label, "Data", validate_fields_for_doctype=False
			)
	if frappe.db.exists("Print Format", NCR_PRINT_FORMAT):
		make_property_setter(
			"Non Conformance",
			None,
			"default_print_format",
			NCR_PRINT_FORMAT,
			"Data",
			for_doctype=True,
			validate_fields_for_doctype=False,
		)
	frappe.clear_cache(doctype="Non Conformance")


def is_custom(fieldname: str) -> bool:
	return bool(frappe.db.exists("Custom Field", {"dt": "Non Conformance", "fieldname": fieldname}))


# ---------------------------------------------------------------- document events
def validate(doc, method=None):
	fill_from_origin(doc)
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
			_("Cannot resolve this NCR until these are completed: {0}").format(", ".join(missing)),
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


BACKFILL_FIELDS = (
	"ncr_date",
	"initiator",
	"initiator_name",
	"source",
	"job_no",
	"contract",
	"drawing_no",
	"lot_qty",
)


def backfill_ncr() -> None:
	"""Existing NCRs: date from creation, initiator from owner, and header fields from the QC unit.

	Only rows without an NCR Date or Initiator Name are touched, so this runs once per record."""
	names = set(frappe.get_all("Non Conformance", filters={"ncr_date": ("is", "not set")}, pluck="name"))
	names |= set(
		frappe.get_all(
			"Non Conformance",
			filters={"initiator": ("is", "set"), "initiator_name": ("is", "not set")},
			pluck="name",
		)
	)
	for name in sorted(names):
		doc = frappe.get_doc("Non Conformance", name)
		before = {f: doc.get(f) for f in BACKFILL_FIELDS}
		fill_from_origin(doc)
		changes = {f: doc.get(f) for f in BACKFILL_FIELDS if doc.get(f) != before[f]}
		if changes:
			frappe.db.set_value("Non Conformance", name, changes, update_modified=False)
