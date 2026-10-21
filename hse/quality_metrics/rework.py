# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""QM-104 Rev. 3 §3.3: in-house findings that do not meet the NCR criteria are Rework, not NCRs.

A Rework is a Non Conformance with Record Type = Rework. It has its own name series
(QA-RW-#####) and an optional Rework No. from the internal log, and its own Rework tab laid
out like the NCR. It still puts the QC unit on QC Hold until it is verified and resolved.
Rework is "rework to specification" by definition, so the NCR disposition and authorization
blocks do not apply. If the criteria turn out to apply, Escalate to NCR raises a formal NCR
and the Rework is closed as Cancelled with a link to it.

Every QC inspection failure raises a Rework. The four criteria are then answered on the
Rework's NCR Criteria Evaluation as it is evaluated: any Yes forces Escalate to NCR, and the
Rework cannot be accepted or resolved until all four are answered No.

The Rework tab fields are the master copy for a Rework. They are mirrored into the matching
NCR fields so the existing closure rules, QC hold and reports keep working unchanged.
"""

import json

import frappe
from frappe import _
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.model.naming import make_autoname
from frappe.utils import cstr, now_datetime, nowdate

NCR = "NCR"
REWORK = "Rework"
RECORD_TYPES = (NCR, REWORK)
REWORK_SERIES = "QA-RW-.#####"
REWORK_PRINT_FORMAT = "QM-104 Rework Report"
NOT_REWORK = "eval:doc.record_type!='Rework'"
IS_REWORK = "eval:doc.record_type=='Rework'"

# QM-104 Rev. 3 §3.3 in-house NCR criteria: any one applies -> NCR.
CRITERIA = {
	"crit_scrap": "Results in scrap of a finished part",
	"crit_cannot_rework": (
		"Can't be reworked to the drawing or spec (needs use-as-is, repair or deviation per QM-144, "
		"or Engineering or customer approval)"
	),
	"crit_customer_safety": "Affects a customer requirement, safety or the promised ship date",
	"crit_supplier": "Supplier caused or contributed, or suspected counterfeit (QM-134 / QM-310)",
}

# NCR Criteria Evaluation on the Rework tab (Yes/No) -> criterion.
EVAL = {f"rw_{c}": c for c in CRITERIA}
YES, NO = "Yes", "No"

# Rework tab field -> matching NCR field.
MIRROR = {
	"rework_date": "ncr_date",
	"rw_initiator": "initiator",
	"rw_initiator_name": "initiator_name",
	"rw_contract": "contract",
	"rw_drawing_no": "drawing_no",
	"rw_source": "source",
	"rw_job_no": "job_no",
	"rw_lot_qty": "lot_qty",
	"rw_reject_qty": "reject_qty",
	"rw_requirement": "details",
	"rw_cause": "cause",
	"rw_rework_performed": "corrective_action",
	"rw_quality_verification": "quality_verification",
	"rw_verification_comments": "verification_comments",
	"rw_inspected_by": "verified_by",
	"rw_inspected_date": "verification_date",
	"rw_approved_by": "approved_by",
	"rw_approved_date": "approved_date",
}

# Sections of the NCR (standard and custom) that do not apply to a Rework.
NCR_ONLY_SECTIONS = ("section_break_4",)


EVAL_HELP = (
	"Answer all four as the rework is evaluated. Any Yes: this must become a formal NCR "
	"(Create > Escalate to NCR). The Rework cannot be accepted or resolved until all four are No."
)


def get_custom_fields(sources: tuple) -> list[dict]:
	crit = [
		{
			"fieldname": "ncr_criteria_section",
			"label": "QM-104 In-House NCR Criteria",
			"fieldtype": "Section Break",
			"insert_after": "escalated_from",
			"collapsible": 0,
			"depends_on": NOT_REWORK,
			"description": (
				"Any one applies: formal NCR (Red QC Hold/Quarantine Tag). None applies: Rework "
				"(Yellow QC Rework Tag); it is not an NCR. Work stops until either is resolved."
			),
		}
	]
	prev = "ncr_criteria_section"
	for i, (fieldname, label) in enumerate(CRITERIA.items()):
		if i == 2:
			crit.append(
				{"fieldname": "ncr_criteria_column", "fieldtype": "Column Break", "insert_after": prev}
			)
			prev = "ncr_criteria_column"
		crit.append(
			{
				"fieldname": fieldname,
				"label": label,
				"fieldtype": "Check",
				"insert_after": prev,
				"no_copy": 1,
			}
		)
		prev = fieldname

	top = [
		{
			"fieldname": "record_type",
			"label": "Record Type",
			"fieldtype": "Select",
			"options": "\n".join(RECORD_TYPES),
			"default": NCR,
			"insert_after": "resolved_on",
			"in_list_view": 1,
			"in_standard_filter": 1,
			"bold": 1,
			"set_only_once": 1,
			"description": "NCR or Rework, per the QM-104 in-house NCR criteria.",
		},
		{
			"fieldname": "escalated_from",
			"label": "Escalated From Rework",
			"fieldtype": "Link",
			"options": "Non Conformance",
			"insert_after": "record_type",
			"read_only": 1,
			"no_copy": 1,
			"depends_on": "eval:doc.escalated_from",
		},
	]

	def f(fieldname, label, fieldtype, after, **kw):
		return {"fieldname": fieldname, "label": label, "fieldtype": fieldtype, "insert_after": after, **kw}

	tab = [
		f("rework_tab", "Rework", "Tab Break", "qc_reinspection", depends_on=IS_REWORK),
		f("rw_info_section", "Rework Information", "Section Break", "rework_tab"),
		f("rework_date", "Date", "Date", "rw_info_section", default="Today"),
		f(
			"rework_no",
			"Rework No.",
			"Data",
			"rework_date",
			in_standard_filter=1,
			search_index=1,
			no_copy=1,
			description="Number from the internal rework log (Nonconformance & Improvement Tracking).",
		),
		f("rw_initiator", "Initiator", "Link", "rework_no", options="User", default="__user"),
		f(
			"rw_initiator_name",
			"Initiator Name",
			"Data",
			"rw_initiator",
			fetch_from="rw_initiator.full_name",
			read_only=1,
		),
		f("rw_contract", "Contract", "Data", "rw_initiator_name"),
		f("rw_drawing_no", "Drawing No.", "Data", "rw_contract"),
		f("rw_source", "Source", "Select", "rw_drawing_no", options="\n" + "\n".join(sources)),
		f("rw_info_column", None, "Column Break", "rw_source"),
		f("rw_job_no", "Job No.", "Data", "rw_info_column"),
		f("rw_lot_qty", "Lot Quantity", "Float", "rw_job_no"),
		f("rw_reject_qty", "Reject Quantity", "Float", "rw_lot_qty"),
		f(
			"rw_eval_section",
			"NCR Criteria Evaluation (QM-104)",
			"Section Break",
			"rw_reject_qty",
			description=EVAL_HELP,
		),
	]
	prev = "rw_eval_section"
	for i, (fieldname, crit_key) in enumerate(EVAL.items()):
		if i == 2:
			tab.append(f("rw_eval_column", None, "Column Break", prev))
			prev = "rw_eval_column"
		tab.append(
			f(fieldname, CRITERIA[crit_key] + "?", "Select", prev, options=f"\n{NO}\n{YES}", no_copy=1)
		)
		prev = fieldname
	tab += [
		f("rw_evaluated_by", "Evaluated By", "Link", prev, options="User", read_only=1, no_copy=1),
		f("rw_evaluated_on", "Evaluated On", "Datetime", "rw_evaluated_by", read_only=1, no_copy=1),
		f("rw_details_section", "Rework Details", "Section Break", "rw_evaluated_on"),
		f(
			"rw_requirement",
			"Quality Requirement Not Met",
			"Text Editor",
			"rw_details_section",
			description="As detailed on the Yellow QC Rework Tag.",
		),
		f("rw_cause", "Cause", "Text Editor", "rw_requirement"),
		f("rw_rework_performed", "Rework Performed", "Text Editor", "rw_cause"),
		f("rw_verification_section", "Verification of Rework", "Section Break", "rw_rework_performed"),
		f(
			"rw_quality_verification",
			"Quality Verification",
			"Select",
			"rw_verification_section",
			options="\nAccept\nReject",
			description="Must be Accept to resolve.",
		),
		f("rw_verification_comments", "Comments", "Small Text", "rw_quality_verification"),
		f("rw_verification_column", None, "Column Break", "rw_verification_comments"),
		f("rw_inspected_by", "Inspected By", "Link", "rw_verification_column", options="Employee"),
		f("rw_inspected_date", "Inspected Date", "Date", "rw_inspected_by"),
		f("rw_approved_by", "Approved By", "Link", "rw_inspected_date", options="Employee"),
		f("rw_approved_date", "Approved Date", "Date", "rw_approved_by"),
		f(
			"escalated_to",
			"Escalated to NCR",
			"Link",
			"rw_approved_date",
			options="Non Conformance",
			read_only=1,
			no_copy=1,
			depends_on="eval:doc.escalated_to",
		),
	]
	for row in tab:
		if row["label"] is None:
			row.pop("label")
	return top + crit + tab


def setup_rework(module: str, sources: tuple) -> None:
	"""Called from setup_ncr before the NCR fields (they follow the criteria) and before CAPA."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	rows = get_custom_fields(sources)
	for row in rows:
		row["module"] = module
	create_custom_fields({"Non Conformance": rows}, update=True)
	for fieldname in NCR_ONLY_SECTIONS:
		make_property_setter(
			"Non Conformance", fieldname, "depends_on", NOT_REWORK, "Data", validate_fields_for_doctype=False
		)
	# Existing records are NCRs.
	frappe.db.sql(
		"update `tabNon Conformance` set record_type=%s where ifnull(record_type, '')=''",
		NCR,
	)
	frappe.clear_cache(doctype="Non Conformance")


# ---------------------------------------------------------------- helpers
def is_rework(doc_or_name) -> bool:
	if isinstance(doc_or_name, str):
		return frappe.db.get_value("Non Conformance", doc_or_name, "record_type") == REWORK
	return doc_or_name.get("record_type") == REWORK


def criteria_met(values: dict) -> list[str]:
	"""Criteria fields answered Yes (inspection Select) or ticked (NCR Check)."""
	return [f for f in CRITERIA if values.get(f) in (1, "1", "Yes", True)]


def evaluation(doc) -> tuple[list[str], list[str]]:
	"""Rework NCR Criteria Evaluation: (criteria answered Yes, criteria not answered)."""
	yes = [c for f, c in EVAL.items() if doc.get(f) == YES]
	unanswered = [c for f, c in EVAL.items() if doc.get(f) not in (YES, NO)]
	return yes, unanswered


def description_values(name: str, html: str) -> dict:
	"""The deficiency description, written to the Rework tab too when the record is a Rework."""
	values = {"details": html}
	if is_rework(name):
		values["rw_requirement"] = html
	return values


def label(doc_or_name) -> str:
	return _("Rework") if is_rework(doc_or_name) else _("Non Conformance")


# ---------------------------------------------------------------- document events
def before_insert(doc, method=None):
	if doc.get("record_type") == REWORK:
		doc.name = make_autoname(REWORK_SERIES, doc=doc)
		doc.flags.name_set = True


def validate(doc, method=None):
	"""Runs from ncr.validate, before the NCR rules."""
	if not doc.get("record_type"):
		doc.record_type = NCR
	if doc.record_type != REWORK:
		return
	yes, unanswered = evaluation(doc)
	met = list(dict.fromkeys(criteria_met(doc.as_dict()) + yes))
	if met and not doc.get("escalated_to"):
		frappe.throw(
			_(
				"This meets the QM-104 NCR criteria ({0}). Use Create > Escalate to NCR to raise the formal NCR."
			).format("; ".join(_(CRITERIA[f]) for f in met)),
			title=_("NCR Required"),
		)
	stamp_evaluation(doc, unanswered)
	sync_mirror(doc)
	accepting = doc.get("rw_quality_verification") == "Accept" and (
		doc.is_new() or doc.has_value_changed("rw_quality_verification")
	)
	resolving = doc.status == "Resolved" and (doc.is_new() or doc.has_value_changed("status"))
	if unanswered and (accepting or resolving):
		frappe.throw(
			_("Complete the NCR Criteria Evaluation on the Rework tab first: {0}").format(
				"; ".join(_(CRITERIA[c]) for c in unanswered)
			),
			title=_("NCR Criteria Evaluation Required"),
		)
	doc.disposition = "Rework to Specification"
	from hse.quality_metrics.ncr import validate_log_number

	validate_log_number(doc, "rework_no", _("Rework No."))


def stamp_evaluation(doc, unanswered: list[str]) -> None:
	"""Who completed the evaluation and when; cleared if an answer is taken back."""
	if unanswered:
		doc.rw_evaluated_by = doc.rw_evaluated_on = None
	elif doc.is_new() or not doc.get("rw_evaluated_by") or any(doc.has_value_changed(f) for f in EVAL):
		doc.rw_evaluated_by = frappe.session.user
		doc.rw_evaluated_on = now_datetime()


def sync_mirror(doc) -> None:
	"""Rework tab is the master; an NCR field changed by code (e.g. a QC re-inspection or the
	missing-parts list) flows back to the Rework tab."""
	new = doc.is_new()
	for rw, ncr in MIRROR.items():
		rv, nv = doc.get(rw), doc.get(ncr)
		if new:
			if rv in (None, "") and nv not in (None, ""):
				doc.set(rw, nv)
			else:
				doc.set(ncr, rv)
		elif doc.has_value_changed(rw):
			doc.set(ncr, rv)
		elif doc.has_value_changed(ncr):
			doc.set(rw, nv)
		elif rv != nv:
			doc.set(ncr, rv)


# ---------------------------------------------------------------- escalation
@frappe.whitelist(methods=["POST"])
def escalate_to_ncr(name: str, criteria: str | list, reason: str | None = None) -> str:
	"""Raise a formal NCR from an open Rework and close the Rework (Cancelled, linked)."""
	rw = frappe.get_doc("Non Conformance", name)
	rw.check_permission("write")
	frappe.has_permission("Non Conformance", "create", throw=True)
	if rw.record_type != REWORK or rw.status != "Open":
		frappe.throw(_("Only an open Rework can be escalated to an NCR."))
	if isinstance(criteria, str):
		criteria = json.loads(criteria) if criteria.strip().startswith("[") else [criteria]
	criteria = [c for c in criteria if c in CRITERIA]
	if not criteria:
		frappe.throw(_("Select at least one QM-104 NCR criterion that applies."))

	details = cstr(rw.rw_requirement)
	if cstr(reason).strip():
		details += "<p><b>{0}</b> {1}</p>".format(
			_("Escalated from Rework {0}:").format(rw.name), frappe.utils.escape_html(reason.strip())
		)
	values = {
		"doctype": "Non Conformance",
		"record_type": NCR,
		"escalated_from": rw.name,
		"status": "Open",
		"subject": cstr(rw.subject).replace("QC rework", "QC failure") or rw.name,
		"ncr_date": nowdate(),
		"initiator": frappe.session.user,
		"details": details,
		"cause": rw.rw_cause,
		"corrective_action": rw.rw_rework_performed,
	}
	for fieldname in (
		"procedure",
		"process_owner",
		"severity",
		"interim_control",
		"qc_unit",
		"qc_inspection",
		"asset",
		"asset_inspection",
		"housekeeping_area",
		"housekeeping_inspection",
	):
		if rw.get(fieldname):
			values[fieldname] = rw.get(fieldname)
	for rwf, ncrf in (
		("rw_contract", "contract"),
		("rw_drawing_no", "drawing_no"),
		("rw_source", "source"),
		("rw_job_no", "job_no"),
		("rw_lot_qty", "lot_qty"),
		("rw_reject_qty", "reject_qty"),
	):
		values[ncrf] = rw.get(rwf)
	for c in criteria:
		values[c] = 1
	nc = frappe.get_doc(values)
	nc.insert()

	# Everything that pointed at the Rework now points at the NCR.
	from hse.quality_metrics.ncr import NCR_SOURCE_LINKS

	for doctype, field in NCR_SOURCE_LINKS:
		if frappe.db.has_column(doctype, field):
			for row in frappe.get_all(doctype, filters={field: rw.name}, pluck="name"):
				frappe.db.set_value(doctype, row, field, nc.name, update_modified=False)

	rw.escalated_to = nc.name
	rw.status = "Cancelled"
	for c in criteria:
		rw.set(f"rw_{c}", YES)
	rw.save()
	rw.add_comment("Info", _("Escalated to NCR {0}.").format(nc.name))
	nc.add_comment("Info", _("Escalated from Rework {0}.").format(rw.name))
	if nc.qc_unit:
		from hse.shop_qc.utils import update_unit_status

		update_unit_status(nc.qc_unit)
	return nc.name
