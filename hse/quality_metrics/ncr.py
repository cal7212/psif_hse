# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""QM-104 Non-Conformance Report (NCR) rules for the Nonconformance Report doctype.

Fills what can be derived from the originating QC unit or inspection, keeps the log numbers
unique, and enforces the form's closure rules.
"""

import frappe
from frappe import _
from frappe.model import no_value_fields, table_fields
from frappe.utils import add_days, cstr, getdate, nowdate

NCR_PRINT_FORMAT = "QM-104 Non-Conformance Report"
# QM-400 5.3 / 8.7.2 d: the roles that decide a nonconformity's disposition and verify it.
QUALITY_ROLES = ("Quality Manager", "System Manager")
# QM-400 Appendix C: days from the NCR date to its target close date, by severity.
DUE_DAYS = {"Critical": 7, "High": 14}
DEFAULT_DUE_DAYS = 30
# Fields only a Quality role may set (QM-400 8.7.2 d, 10.2.1 d).
QUALITY_ONLY_FIELDS = ("auth_quality_manager", "quality_verification", "capa_quality_verification")
# Fields that stay editable on a Resolved record: the CAPA and SCAR run on after the NCR closes,
# and links written back by re-inspections.
UNLOCKED_ON_RESOLVE = {
	"status",
	"resolved_on",
	"reopen_reason",
	"capa_related_ncrs",
	"qc_reinspection",
	"reinspection",
	"housekeeping_reinspection",
	"escalated_to",
}
UNLOCKED_PREFIXES = ("capa_", "scar_", "why_")
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
	"Calibration",
	OTHER,
)


# ---------------------------------------------------------------- document events
def validate(doc, method=None):
	from hse.quality_metrics import rework

	protect_resolved(doc)  # before anything below fills blanks on an old record
	check_quality_only_fields(doc)
	fill_from_origin(doc)
	set_due_date(doc)
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
	if is_product_ncr(doc):
		missing += product_closure_gaps(doc)
	if missing:
		frappe.throw(
			_("Cannot resolve this {0} until these are completed: {1}").format(
				_("Rework") if doc.get("record_type") == "Rework" else _("NCR"), ", ".join(missing)
			),
			title=_("Resolution Blocked"),
		)


def is_product_ncr(doc) -> bool:
	"""An NCR on product or service conformity (QM-400 8.7), as opposed to a Rework record or an
	equipment / housekeeping finding raised from the OH&S inspections."""
	return (
		doc.get("record_type") != "Rework"
		and not doc.get("asset_inspection")
		and not doc.get("housekeeping_inspection")
		and doc.get("source") not in ("Asset Inspection", "Housekeeping Inspection")
	)


def has_quality_role(user: str | None = None) -> bool:
	return bool(set(frappe.get_roles(user)) & set(QUALITY_ROLES))


def system_save() -> bool:
	return bool(frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch)


def employee_user(employee: str | None) -> str | None:
	return frappe.db.get_value("Employee", employee, "user_id") if employee else None


def product_closure_gaps(doc) -> list[str]:
	"""QM-400 8.7.1 c-d and 8.7.2 d: who decided, who was told, and the concession on file."""
	missing = []
	if not doc.get("auth_quality_manager"):
		missing.append(_("Quality Manager authorization of the disposition"))
	if doc.get("disposition") in CUSTOMER_APPROVAL and not doc.get("customer_concession"):
		missing.append(_("Customer Concession attachment"))
	if (doc.get("source") == "Customer" or doc.get("crit_customer_safety")) and not doc.get(
		"customer_notified_on"
	):
		missing.append(_("Customer Notified On"))
	if doc.get("source") == "Customer" and not doc.get("complaint_acknowledged_on"):
		missing.append(_("Acknowledged On (customer complaint)"))
	verifier = employee_user(doc.get("verified_by"))
	if verifier and verifier == doc.get("initiator"):
		missing.append(_("an inspector other than the initiator to verify the correction"))
	return missing


def set_due_date(doc) -> None:
	"""Target close date from the severity, unless someone set it."""
	if doc.get("ncr_due_date") or not doc.get("ncr_date") or doc.get("record_type") == "Rework":
		return
	doc.ncr_due_date = add_days(doc.ncr_date, DUE_DAYS.get(doc.get("severity"), DEFAULT_DUE_DAYS))


def protect_resolved(doc) -> None:
	"""QM-400 7.5.3: a resolved record is evidence. Only a Quality role may reopen or cancel it,
	with a reason, and its NCR fields cannot be edited while it stays resolved. The CAPA and
	SCAR sections remain open: they run on after the NCR closes."""
	before = None if doc.is_new() else doc.get_doc_before_save()
	if not before or before.status != "Resolved" or system_save():
		return
	if doc.status != "Resolved":
		if not has_quality_role():
			frappe.throw(
				_("Only a Quality Manager can reopen or cancel a resolved record."),
				title=_("Record Locked"),
			)
		if not cstr(doc.get("reopen_reason")).strip() or not doc.has_value_changed("reopen_reason"):
			frappe.throw(_("Enter a new Reopen Reason."), title=_("Reason Required"))
		doc.add_comment(
			"Info",
			_("Changed from Resolved to {0}: {1}").format(_(doc.status), cstr(doc.reopen_reason).strip()),
		)
		return
	changed = [
		df.label or df.fieldname
		for df in doc.meta.fields
		if df.fieldtype not in no_value_fields
		and df.fieldtype not in table_fields
		and df.fieldname not in UNLOCKED_ON_RESOLVE
		and not df.fieldname.startswith(UNLOCKED_PREFIXES)
		and cstr(doc.get(df.fieldname)) != cstr(before.get(df.fieldname))
	]
	if changed and not has_quality_role():
		frappe.throw(
			_("This record is resolved; reopen it to change: {0}").format(", ".join(changed[:5])),
			title=_("Record Locked"),
		)


def check_quality_only_fields(doc) -> None:
	"""Disposition authority and verification of effectiveness belong to Quality (QM-400 5.3)."""
	if system_save() or has_quality_role():
		return
	before = None if doc.is_new() else doc.get_doc_before_save()
	for field in QUALITY_ONLY_FIELDS:
		if field == "quality_verification" and not is_product_ncr(doc):
			continue
		old = before.get(field) if before else None
		if cstr(doc.get(field)) != cstr(old) and doc.get(field):
			frappe.throw(
				_("{0} can only be entered by a Quality Manager.").format(_(doc.meta.get_label(field))),
				title=_("Not Permitted"),
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
