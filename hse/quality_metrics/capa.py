# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""QM-128 Corrective Action & Preventative Action (CAPA) on the Non Conformance doctype.

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
CAPA_DEP = "eval:doc.capa_required"


def why_fields() -> list[dict]:
	rows = []
	after = "why_problem"
	for n in range(1, WHYS + 1):
		rows.append(
			{
				"fieldname": f"why_{n}",
				"label": f"Why {n}?",
				"fieldtype": "Small Text",
				"insert_after": after,
				"description": "Why did the problem occur?" if n == 1 else "Why did the answer above happen?",
			}
		)
		after = f"why_{n}"
	return rows


def get_custom_fields() -> list[dict]:
	return [
		{
			"fieldname": "capa_tab",
			"label": "CAPA",
			"fieldtype": "Tab Break",
			"insert_after": "qc_reinspection",
		},
		{
			"fieldname": "capa_required",
			"label": "CAPA Required",
			"fieldtype": "Check",
			"insert_after": "capa_tab",
			"in_standard_filter": 1,
			"description": "QM-128: raise a CAPA for trended NCRs (more than 5 similar failures) or when Quality requires one.",
		},
		# ------------------------------------------------------------- header
		{
			"fieldname": "capa_header_section",
			"label": "CAPA Report",
			"fieldtype": "Section Break",
			"insert_after": "capa_required",
			"depends_on": CAPA_DEP,
		},
		{
			"fieldname": "capa_no",
			"label": "CAPA #",
			"fieldtype": "Data",
			"no_copy": 1,
			"in_standard_filter": 1,
			"search_index": 1,
			"insert_after": "capa_header_section",
			"mandatory_depends_on": CAPA_DEP,
			"description": "Number from the internal CAPA log.",
		},
		{
			"fieldname": "capa_status",
			"label": "CAPA Status",
			"fieldtype": "Select",
			"options": "\n" + "\n".join(CAPA_STATUSES),
			"insert_after": "capa_no",
			"in_standard_filter": 1,
		},
		{
			"fieldname": "capa_source",
			"label": "CAPA Source",
			"fieldtype": "Select",
			"options": "\n" + "\n".join(CAPA_SOURCES),
			"insert_after": "capa_status",
		},
		{
			"fieldname": "capa_part_description",
			"label": "Part Number/Description",
			"fieldtype": "Data",
			"insert_after": "capa_source",
		},
		{
			"fieldname": "capa_header_column",
			"fieldtype": "Column Break",
			"insert_after": "capa_part_description",
		},
		{
			"fieldname": "capa_initiated_by",
			"label": "Initiated By",
			"fieldtype": "Link",
			"options": "User",
			"insert_after": "capa_header_column",
		},
		{
			"fieldname": "capa_initiated_by_name",
			"label": "Initiated By Name",
			"fieldtype": "Data",
			"read_only": 1,
			"fetch_from": "capa_initiated_by.full_name",
			"insert_after": "capa_initiated_by",
		},
		{
			"fieldname": "capa_initiated_date",
			"label": "Initiated Date",
			"fieldtype": "Date",
			"insert_after": "capa_initiated_by_name",
		},
		{
			"fieldname": "capa_related_ncrs",
			"label": "Related NCRs",
			"fieldtype": "Table MultiSelect",
			"options": "CAPA Related NCR",
			"insert_after": "capa_initiated_date",
			"description": "Other NCRs with the same failure or failure mode.",
		},
		# ------------------------------------------------------------- assignment and due dates
		{
			"fieldname": "capa_assignment_section",
			"label": "Assignment and Due Dates",
			"fieldtype": "Section Break",
			"insert_after": "capa_related_ncrs",
			"depends_on": CAPA_DEP,
			"description": "Containment due within 7 days of initiation. Correction due 30 days and closure due 60 days "
			"after initiation, unless an extension is approved by the Management Representative.",
		},
		{
			"fieldname": "capa_assigned_to",
			"label": "Assigned To",
			"fieldtype": "Link",
			"options": "Employee",
			"insert_after": "capa_assignment_section",
		},
		{
			"fieldname": "capa_assigned_date",
			"label": "Assigned Date",
			"fieldtype": "Date",
			"insert_after": "capa_assigned_to",
		},
		{
			"fieldname": "capa_extension_approved_by",
			"label": "Extension Approval",
			"fieldtype": "Link",
			"options": "Employee",
			"insert_after": "capa_assigned_date",
			"description": "Management Representative approving the extension.",
		},
		{
			"fieldname": "capa_extended_until",
			"label": "Due Date Extended Until",
			"fieldtype": "Date",
			"insert_after": "capa_extension_approved_by",
		},
		{
			"fieldname": "capa_extension_justification",
			"label": "Justification for Extension",
			"fieldtype": "Small Text",
			"insert_after": "capa_extended_until",
			"depends_on": "eval:doc.capa_extended_until",
			"mandatory_depends_on": "eval:doc.capa_extended_until",
		},
		{
			"fieldname": "capa_due_column",
			"fieldtype": "Column Break",
			"insert_after": "capa_extension_justification",
		},
		{
			"fieldname": "capa_containment_due",
			"label": "Containment Due",
			"fieldtype": "Date",
			"read_only": 1,
			"insert_after": "capa_due_column",
		},
		{
			"fieldname": "capa_correction_due",
			"label": "Correction Due",
			"fieldtype": "Date",
			"read_only": 1,
			"insert_after": "capa_containment_due",
		},
		{
			"fieldname": "capa_closure_due",
			"label": "Closure Due",
			"fieldtype": "Date",
			"read_only": 1,
			"insert_after": "capa_correction_due",
		},
		# ------------------------------------------------------------- finding and containment
		{
			"fieldname": "capa_finding_section",
			"label": "Finding and Containment",
			"fieldtype": "Section Break",
			"insert_after": "capa_closure_due",
			"depends_on": CAPA_DEP,
		},
		{
			"fieldname": "capa_finding",
			"label": "Finding",
			"fieldtype": "Text Editor",
			"insert_after": "capa_finding_section",
			"description": "Filled from the Deficiency Description when blank.",
		},
		{
			"fieldname": "capa_containment",
			"label": "Containment/Correction",
			"fieldtype": "Text Editor",
			"insert_after": "capa_finding",
			"description": "Filled from the NCR Correction when blank.",
		},
		# ------------------------------------------------------------- 5 whys
		{
			"fieldname": "capa_whys_section",
			"label": "5 Whys Root Cause Analysis",
			"fieldtype": "Section Break",
			"insert_after": "capa_containment",
			"depends_on": CAPA_DEP,
			"description": "Start from the problem and ask why until the root cause is reached. Stop early if the "
			"root cause is found before the fifth why.",
		},
		{
			"fieldname": "why_problem",
			"label": "Problem Statement",
			"fieldtype": "Small Text",
			"insert_after": "capa_whys_section",
			"description": "What happened, where and when. Filled from the NCR subject when blank.",
		},
		*why_fields(),
		{
			"fieldname": "capa_root_cause",
			"label": "Root Cause",
			"fieldtype": "Text Editor",
			"insert_after": f"why_{WHYS}",
			"description": "Filled from the last answered why when blank.",
		},
		{
			"fieldname": "capa_human_factor",
			"label": "Contributing Human Factor if applicable",
			"fieldtype": "Small Text",
			"insert_after": "capa_root_cause",
		},
		# ------------------------------------------------------------- actions and verification
		{
			"fieldname": "capa_action_section",
			"label": "Corrective and Preventive Action",
			"fieldtype": "Section Break",
			"insert_after": "capa_human_factor",
			"depends_on": CAPA_DEP,
		},
		{
			"fieldname": "capa_corrective_action",
			"label": "Corrective Action",
			"fieldtype": "Text Editor",
			"insert_after": "capa_action_section",
			"description": "Action that eliminates the root cause. The NCR Correction is the immediate fix.",
		},
		{
			"fieldname": "capa_preventive_action",
			"label": "Preventive Action",
			"fieldtype": "Text Editor",
			"insert_after": "capa_corrective_action",
			"description": "Filled from the NCR Preventive Action when blank.",
		},
		{
			"fieldname": "capa_verification_section",
			"label": "Verification and Closure",
			"fieldtype": "Section Break",
			"insert_after": "capa_preventive_action",
			"depends_on": CAPA_DEP,
		},
		{
			"fieldname": "capa_quality_verification",
			"label": "Quality Verification",
			"fieldtype": "Select",
			"options": "\nEffective\nNot Effective",
			"insert_after": "capa_verification_section",
			"description": "Effectiveness of the corrective action. Must be Effective to close.",
		},
		{
			"fieldname": "capa_verified_by",
			"label": "Verified By",
			"fieldtype": "Link",
			"options": "Employee",
			"insert_after": "capa_quality_verification",
		},
		{
			"fieldname": "capa_verification_date",
			"label": "Verification Date",
			"fieldtype": "Date",
			"insert_after": "capa_verified_by",
		},
		{
			"fieldname": "capa_follow_up",
			"label": "Follow-Up",
			"fieldtype": "Small Text",
			"insert_after": "capa_verification_date",
		},
		{"fieldname": "capa_closure_column", "fieldtype": "Column Break", "insert_after": "capa_follow_up"},
		{
			"fieldname": "capa_closed_by",
			"label": "Closed By",
			"fieldtype": "Link",
			"options": "Employee",
			"insert_after": "capa_closure_column",
		},
		{
			"fieldname": "capa_closure_date",
			"label": "Closure Date",
			"fieldtype": "Date",
			"insert_after": "capa_closed_by",
		},
	]


def setup_capa(module: str) -> None:
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	rows = get_custom_fields()
	for row in rows:
		row["module"] = module
	create_custom_fields({"Non Conformance": rows}, update=True)
	frappe.clear_cache(doctype="Non Conformance")


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
