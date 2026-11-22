# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Job Hazard Analysis (OSHA 3071): the job broken into steps, the hazards of each step and the
controls, with the risk that remains with the controls rated on the risk assessment matrix.

Submitting approves the JHA. Like a risk assessment it is changed by revision (Start Review),
and from an approved JHA the permits it calls for can be drafted."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cint, today

from hse.hse.doctype.risk_assessment.risk_assessment import CRITICAL, has_text, risk_rating, risk_score
from hse.hse.revisions import ACTIVE, DRAFT, RevisionMixin, revision_postprocess

DOCTYPE = "Job Hazard Analysis"


def score_step(row):
	row.risk_score = risk_score(row.severity, row.likelihood)
	row.risk_rating = risk_rating(row.risk_score)


def approval_errors(doc) -> list[str]:
	errors = []
	if not doc.steps:
		errors.append(_("Add the job steps."))
	for row in doc.steps:
		tag = _("Step {0}").format(row.idx)
		if not has_text(row.hazards):
			errors.append(_("{0}: record the hazards, or write None identified.").format(tag))
		if not has_text(row.controls):
			errors.append(_("{0}: record the controls.").format(tag))
		if not row.risk_score:
			errors.append(_("{0}: rate the severity and likelihood with the controls.").format(tag))
		elif row.risk_rating == CRITICAL:
			errors.append(
				_("{0} is still Critical with the controls. Change the job before approving.").format(tag)
			)
	if not doc.next_review_date:
		errors.append(_("Set the review interval or the Next Review Due date."))
	return errors


class JobHazardAnalysis(RevisionMixin, Document):
	PREVIOUS_FIELD = "previous_analysis"
	DATE_FIELD = "analysis_date"

	def validate(self):
		if self.docstatus == 0:
			self.status = DRAFT
		self.validate_previous()
		self.set_next_review_date()
		for row in self.steps:
			score_step(row)
		self.highest_risk_score = max((cint(r.risk_score) for r in self.steps), default=0)
		self.highest_risk_rating = risk_rating(self.highest_risk_score)

	def before_submit(self):
		if errors := approval_errors(self):
			frappe.throw("<br>".join(errors), title=_("Cannot Approve"))
		self.status = ACTIVE
		self.approved_by = frappe.session.user
		self.approved_on = today()

	def on_submit(self):
		self.supersede_previous()

	def before_update_after_submit(self):
		self.validate_review_date()

	def on_cancel(self):
		self.cancel_revision()


@frappe.whitelist()
def make_review(source_name: str, target_doc: str | dict | None = None):
	"""The next revision of an approved JHA, as a draft."""

	def postprocess(source, target):
		revision_postprocess(source, target, "previous_analysis", "analysis_date", today())
		target.prepared_by = (
			frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
			or source.prepared_by
		)
		for row in target.steps:
			score_step(row)
		for row in target.workers:
			row.briefed = 0  # workers go through the new revision again

	return get_mapped_doc(
		DOCTYPE,
		source_name,
		{
			DOCTYPE: {
				"doctype": DOCTYPE,
				"validation": {"docstatus": ["=", 1], "status": ["=", ACTIVE]},
				"field_no_map": ["status", "superseded_by", "next_review_date"],
			},
			"Job Hazard Analysis Step": {"doctype": "Job Hazard Analysis Step"},
			"Permit Worker": {"doctype": "Permit Worker"},
		},
		target_doc,
		postprocess,
	)
