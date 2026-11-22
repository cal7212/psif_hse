# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Energized Electrical Work Permit: the permit of NFPA 70E 130.2(B)(2).

Submitting the permit approves the energized work. Approval needs every element of
130.2(B)(2): the equipment and work, why it must be done energized, the shock and arc flash risk
assessments, the safe work practices, how unqualified persons are kept out, and a job briefing
with every worker. The person approving cannot be the requester."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from hse.hse.permits import has_text, warn_unqualified, window_errors, workers_with_role

DRAFT, APPROVED, CANCELLED = "Draft", "Approved", "Cancelled"
QUALIFIED_PERSON = "Qualified Person"
INCIDENT_ENERGY_METHOD = "Incident Energy Analysis"
# Company rule: energized work above this incident energy is not approved; de-energize instead.
MAX_INCIDENT_ENERGY = 40  # cal/cm²
ACCESS_CHECKS = ("acc_barricade", "acc_signs", "acc_attendant")
# Elements of 130.2(B)(2) that are free text on the permit.
REQUIRED_TEXT = (
	"justification_type",
	"justification",
	"nominal_voltage",
	"limited_approach",
	"restricted_approach",
	"shock_ppe",
	"arc_flash_boundary",
	"arc_flash_ppe",
	"safe_work_practices",
)


def approval_errors(doc) -> list[str]:
	errors = window_errors(doc, "work_start", "work_end", issuing=True)
	errors += [
		_("Complete {0}.").format(_(doc.meta.get_label(field)))
		for field in REQUIRED_TEXT
		if not has_text(doc.get(field))
	]
	if not doc.esc_not_feasible:
		errors.append(_("Confirm that an electrically safe work condition cannot be established."))
	if doc.arc_method == INCIDENT_ENERGY_METHOD:
		if not flt(doc.incident_energy) or not has_text(doc.working_distance):
			errors.append(_("Enter the incident energy and the working distance it was calculated at."))
		elif flt(doc.incident_energy) > MAX_INCIDENT_ENERGY:
			errors.append(
				_(
					"Incident energy above {0} cal/cm²: energized work is not approved. De-energize the equipment."
				).format(MAX_INCIDENT_ENERGY)
			)
	elif not doc.ppe_category:
		errors.append(_("Select the arc flash PPE category."))
	if not any(doc.get(f) for f in ACCESS_CHECKS) and not has_text(doc.access_other):
		errors.append(_("Record how unqualified persons are kept out of the work area."))
	if not workers_with_role(doc.workers, QUALIFIED_PERSON):
		errors.append(_("Name at least one worker with the role Qualified Person."))
	if not doc.briefing_done:
		errors.append(_("Hold the job briefing, covering the job-specific hazards, before approval."))
	not_briefed = [w.worker_name for w in doc.workers if not w.briefed]
	if not_briefed:
		errors.append(_("Not yet briefed: {0}.").format(", ".join(not_briefed)))
	return errors


class EnergizedElectricalWorkPermit(Document):
	def validate(self):
		if self.docstatus == 0:
			self.status = DRAFT
		if self.briefing_done and not self.briefing_time:
			self.briefing_time = now_datetime()
		if errors := window_errors(self, "work_start", "work_end"):
			frappe.throw("<br>".join(errors), title=_("Energized Electrical Work Permit"))

	def before_submit(self):
		if errors := approval_errors(self):
			frappe.throw("<br>".join(errors), title=_("Cannot Approve"))
		self.check_not_self_approval()
		self.status = APPROVED
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()

	def on_submit(self):
		warn_unqualified(self, "70E", (QUALIFIED_PERSON,), _("NFPA 70E qualified electrical work"))

	def on_cancel(self):
		self.db_set("status", CANCELLED)

	def check_not_self_approval(self):
		requester_user = frappe.db.get_value("Employee", self.requested_by, "user_id")
		if requester_user and requester_user == frappe.session.user:
			frappe.throw(
				_("Energized work is approved by someone other than the requester."),
				title=_("Cannot Approve"),
			)


@frappe.whitelist()
def make_from_jha(source_name: str):
	"""A draft permit from an approved Job Hazard Analysis."""
	jha = frappe.get_doc("Job Hazard Analysis", source_name)
	jha.check_permission("read")
	doc = frappe.new_doc("Energized Electrical Work Permit")
	doc.update(
		{
			"company": jha.company,
			"location": jha.location,
			"asset": jha.asset,
			"job_hazard_analysis": jha.name,
			"work_description": jha.job_title,
			"requested_by": jha.supervisor or jha.prepared_by,
		}
	)
	return doc
