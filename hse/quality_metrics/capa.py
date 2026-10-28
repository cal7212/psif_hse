# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""QM-128 Corrective Action & Preventative Action (CAPA) on the Nonconformance Report doctype.

A CAPA tab on the NCR holds the QM-128 report fields and a 5 Whys root-cause analysis.
Ticking CAPA Required needs the CAPA # from the internal log, stamps who and when, and fills blanks from the NCR;
due dates follow the QM-128 rule (containment 7 days, correction 30, closure 60, unless an
approved extension moves correction and closure). Closing the CAPA needs a root cause, a
corrective action and an Effective verification.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cstr, getdate, nowdate, strip_html

CAPA_PRINT_FORMAT = "QM-128 CAPA Report"
CAPA_STATUSES = (
	"Open",
	"Containment",
	"Investigation",
	"Corrective Action",
	"Verification",
	"Closed",
	"Cancelled",
)
CAPA_SOURCES = (
	"NCR",
	"NCR Trend",
	"Customer Complaint",
	"Internal Audit",
	"External Audit",
	"Supplier",
	"Management Review",
	"Other",
)
CONTAINMENT_DAYS, CORRECTION_DAYS, CLOSURE_DAYS = 7, 30, 60
WHYS = 5


# ---------------------------------------------------------------- document events
def validate(doc, method=None):
	if not doc.get("capa_required"):
		return
	start_capa(doc)
	fill_from_ncr(doc)
	set_due_dates(doc)
	validate_dates(doc)
	related = [r.non_conformance for r in doc.get("capa_related_ncrs") or []]
	if doc.name in related:
		frappe.throw(_("Related NCRs cannot include this NCR."))
	if doc.capa_status == "Closed" and (doc.is_new() or doc.has_value_changed("capa_status")):
		validate_capa_closure(doc)


def start_capa(doc) -> None:
	from hse.quality_metrics.ncr import validate_log_number

	validate_log_number(doc, "capa_no", _("CAPA #"))
	if not doc.get("capa_no"):
		frappe.throw(_("Enter the CAPA # from the internal CAPA log."), title=_("CAPA # Required"))
	if not doc.get("capa_status"):
		doc.capa_status = "Open"
	if not doc.get("capa_initiated_by"):
		doc.capa_initiated_by = frappe.session.user
	if doc.get("capa_initiated_by") and not doc.get("capa_initiated_by_name"):
		doc.capa_initiated_by_name = frappe.db.get_value("User", doc.capa_initiated_by, "full_name")
	if not doc.get("capa_initiated_date"):
		doc.capa_initiated_date = nowdate()
	if not doc.get("capa_source"):
		doc.capa_source = "NCR Trend" if doc.get("capa_related_ncrs") else "NCR"
	if not doc.get("capa_scar_reference"):
		doc.capa_scar_reference = doc.capa_no


def fill_from_ncr(doc) -> None:
	"""Blank CAPA fields start from what the NCR already records."""
	for target, source in (
		("capa_finding", "details"),
		("capa_containment", "corrective_action"),
		("capa_preventive_action", "preventive_action"),
	):
		if is_blank(doc.get(target)) and not is_blank(doc.get(source)):
			doc.set(target, doc.get(source))
	if not cstr(doc.get("why_problem")).strip() and doc.get("subject"):
		doc.why_problem = doc.subject
	if is_blank(doc.get("capa_root_cause")):
		last = last_why(doc)
		if last:
			doc.capa_root_cause = last
	if not doc.get("capa_part_description") and doc.get("qc_unit"):
		unit = frappe.db.get_value(
			"QC Unit", doc.qc_unit, ["item_code", "model", "description"], as_dict=True
		)
		if unit:
			doc.capa_part_description = " - ".join(
				x for x in (unit.item_code or unit.model, unit.description) if x
			)[:140]


def last_why(doc) -> str | None:
	for n in range(WHYS, 0, -1):
		answer = cstr(doc.get(f"why_{n}")).strip()
		if answer:
			return answer
	return None


def set_due_dates(doc) -> None:
	"""QM-128: containment 7 days, correction 30, closure 60; an approved extension moves correction and closure."""
	if not doc.get("capa_initiated_date"):
		return
	start = getdate(doc.capa_initiated_date)
	doc.capa_containment_due = add_days(start, CONTAINMENT_DAYS)
	correction = add_days(start, CORRECTION_DAYS)
	closure = add_days(start, CLOSURE_DAYS)
	if doc.get("capa_extended_until"):
		extended = getdate(doc.capa_extended_until)
		correction, closure = max(correction, extended), max(closure, extended)
	doc.capa_correction_due = correction
	doc.capa_closure_due = closure


def validate_dates(doc) -> None:
	start = getdate(doc.capa_initiated_date) if doc.get("capa_initiated_date") else None
	if doc.get("capa_extended_until"):
		if not doc.get("capa_extension_approved_by"):
			frappe.throw(_("An extended due date needs the Extension Approval (Management Representative)."))
		if not cstr(doc.get("capa_extension_justification")).strip():
			frappe.throw(_("Enter the Justification for Extension."))
		if start and getdate(doc.capa_extended_until) <= start:
			frappe.throw(_("Due Date Extended Until must be after the Initiated Date."))
	for field, label in (
		("capa_assigned_date", _("Assigned Date")),
		("capa_verification_date", _("Verification Date")),
		("capa_closure_date", _("Closure Date")),
	):
		if start and doc.get(field) and getdate(doc.get(field)) < start:
			frappe.throw(_("{0} cannot be before the Initiated Date.").format(label))


def validate_capa_closure(doc) -> None:
	if not doc.get("capa_closure_date"):
		doc.capa_closure_date = nowdate()
	missing = []
	if not last_why(doc):
		missing.append(_("at least one Why"))
	if is_blank(doc.get("capa_root_cause")):
		missing.append(_("Root Cause"))
	if is_blank(doc.get("capa_corrective_action")):
		missing.append(_("Corrective Action"))
	if doc.get("capa_quality_verification") != "Effective":
		missing.append(_("Quality Verification: Effective"))
	if not doc.get("capa_verified_by"):
		missing.append(_("Verified By"))
	if not doc.get("capa_verification_date"):
		missing.append(_("Verification Date"))
	if not doc.get("capa_closed_by"):
		missing.append(_("Closed By"))
	if missing:
		frappe.throw(
			_("Cannot close this CAPA until these are completed: {0}").format(", ".join(missing)),
			title=_("CAPA Closure Blocked"),
		)


def is_blank(value) -> bool:
	return not strip_html(cstr(value)).strip()
