# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Risk Assessment: hazard identification and risk assessment (ISO 45001 6.1.2).

Each hazard is rated severity x likelihood on a 5 x 5 matrix, first with the controls already in
place (initial risk) and then with the additional controls (residual risk). Submitting the
assessment approves it. Actions can be closed after approval; the hazards cannot change, so a
change is a new revision: Start Review copies the assessment as a draft, and when that is
approved the earlier revision becomes Superseded. Cancelling the new revision puts the earlier
one back in force."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cint, cstr, formatdate, today

from hse.hse.assignments import assign
from hse.hse.doctype.injury_illness_report.injury_illness_report import corrective_action_summary
from hse.hse.revisions import ACTIVE, DRAFT, RevisionMixin, revision_postprocess

DOCTYPE = "Risk Assessment"
# Highest band first: a score at or above the threshold takes that rating. Keep in step with
# RATING_BANDS in risk_assessment.js and the matrix on the print format.
RATING_BANDS = ((20, "Critical"), (10, "High"), (5, "Medium"), (1, "Low"))
RATING_ORDER = {"": 0, "Low": 1, "Medium": 2, "High": 3, "Critical": 4}
HIGH, CRITICAL = "High", "Critical"
# Who gets the review ToDo when the lead assessor has no user.
REVIEW_FALLBACK_ROLE = "Safety Manager"


def level(value) -> int:
	"""1-5 from a matrix option such as "3 - Possible"; 0 when blank or off the scale."""
	text = cstr(value).strip()
	n = cint(text.split(" ", 1)[0]) if text else 0
	return n if 1 <= n <= 5 else 0


def risk_score(severity, likelihood) -> int:
	s, lk = level(severity), level(likelihood)
	return s * lk if s and lk else 0


def risk_rating(score) -> str:
	for threshold, rating in RATING_BANDS:
		if cint(score) >= threshold:
			return rating
	return ""


def has_text(value) -> bool:
	return bool(cstr(value).strip())


def score_hazard(row):
	"""Fill the scores and ratings on one hazard row. Only additional controls can change the
	risk, so without them the residual levels are the initial ones."""
	if not has_text(row.additional_controls):
		row.residual_severity = row.initial_severity
		row.residual_likelihood = row.initial_likelihood
	row.initial_score = risk_score(row.initial_severity, row.initial_likelihood)
	row.initial_rating = risk_rating(row.initial_score)
	row.residual_score = risk_score(row.residual_severity, row.residual_likelihood)
	row.residual_rating = risk_rating(row.residual_score)


def hazard_errors(rows, complete: bool = False) -> list[str]:
	"""Problems with the hazard rows. Always: controls cannot raise the risk. With complete
	(on approval): every hazard rated, and rated again after any additional controls."""
	errors = []
	for row in rows:
		tag = _("Hazard row {0}").format(row.idx)
		if row.initial_score and row.residual_score and row.residual_score > row.initial_score:
			errors.append(
				_(
					"{0}: the residual risk ({1}) is higher than the initial risk ({2}). Additional "
					"controls cannot raise the risk; check the ratings."
				).format(tag, row.residual_score, row.initial_score)
			)
		if not complete:
			continue
		if not row.initial_score:
			errors.append(_("{0}: select the severity and likelihood.").format(tag))
		if has_text(row.additional_controls):
			if not row.residual_score:
				errors.append(
					_(
						"{0}: select the residual severity and likelihood with the additional controls."
					).format(tag)
				)
			if not row.control_type:
				errors.append(_("{0}: select the control type of the additional controls.").format(tag))
	return errors


def action_errors(actions, hazard_count: int) -> list[str]:
	return [
		_("Action row {0}: there is no hazard row {1}.").format(row.idx, row.hazard_no)
		for row in actions
		if cint(row.hazard_no) and not 1 <= cint(row.hazard_no) <= hazard_count
	]


def risk_summary(rows) -> dict:
	initial = max((cint(r.initial_score) for r in rows), default=0)
	residual = max((cint(r.residual_score) for r in rows), default=0)
	return {
		"hazard_count": len(rows),
		"highest_initial_score": initial,
		"highest_initial_rating": risk_rating(initial),
		"highest_residual_score": residual,
		"highest_residual_rating": risk_rating(residual),
		"high_risk_count": sum(
			1 for r in rows if RATING_ORDER.get(cstr(r.residual_rating), 0) >= RATING_ORDER[HIGH]
		),
	}


def approval_errors(doc) -> list[str]:
	"""What stops the assessment being approved. Critical after controls stops the work; High
	after controls can be approved only with a written acceptance of the remaining risk."""
	errors = []
	if not doc.hazards:
		errors.append(_("Add at least one hazard before approving the assessment."))
	errors += hazard_errors(doc.hazards, complete=True)
	critical = [str(r.idx) for r in doc.hazards if r.residual_rating == CRITICAL]
	if critical:
		errors.append(
			_(
				"Hazard row(s) {0} are still Critical after controls. The work must not go ahead until "
				"further controls bring the risk down."
			).format(", ".join(critical))
		)
	elif any(r.residual_rating == HIGH for r in doc.hazards) and not has_text(doc.residual_risk_acceptance):
		errors.append(
			_(
				"Hazards are still High after controls: enter the High Residual Risk Acceptance before approving."
			)
		)
	if not doc.next_review_date:
		errors.append(_("Set the review interval or the Next Review Due date."))
	return errors


class RiskAssessment(RevisionMixin, Document):
	PREVIOUS_FIELD = "previous_assessment"
	DATE_FIELD = "assessment_date"

	def validate(self):
		if self.docstatus == 0:
			self.status = DRAFT
		self.validate_previous()
		self.set_next_review_date()
		for row in self.hazards:
			score_hazard(row)
		self.update(risk_summary(self.hazards))
		if errors := hazard_errors(self.hazards) + action_errors(self.actions, len(self.hazards)):
			frappe.throw("<br>".join(errors), title=_("Risk Assessment"))
		self.set_action_summary()

	def before_submit(self):
		if errors := approval_errors(self):
			frappe.throw("<br>".join(errors), title=_("Cannot Approve"))
		self.status = ACTIVE
		self.approved_by = frappe.session.user
		self.approved_on = today()

	def on_submit(self):
		self.supersede_previous()
		self.assign_actions()

	def before_update_after_submit(self):
		# Actions are usually finished, and reviews brought forward, after approval.
		self.validate_review_date()
		if errors := action_errors(self.actions, len(self.hazards)):
			frappe.throw("<br>".join(errors), title=_("Risk Assessment"))
		self.set_action_summary()

	def on_update_after_submit(self):
		self.assign_actions()

	def on_cancel(self):
		self.cancel_revision()

	def set_action_summary(self):
		self.date_due, self.date_done = corrective_action_summary(self.actions)

	def assign_actions(self):
		"""A ToDo for each person assigned an open action, once the assessment is approved."""
		if self.status != ACTIVE:
			return
		users = [r.assigned_to for r in self.actions if r.assigned_to and not r.date_done]
		if users:
			assign(
				users,
				DOCTYPE,
				self.name,
				_("Complete your actions on risk assessment {0}").format(self.title),
			)


@frappe.whitelist()
def make_review(source_name: str, target_doc: str | dict | None = None):
	"""The next revision of an approved assessment, as a draft: hazards, team and open actions
	carried over, approval and review date cleared."""

	def postprocess(source, target):
		revision_postprocess(source, target, "previous_assessment", "assessment_date", today())
		target.review_trigger = "Scheduled Review"
		target.injury_report = None
		target.assessed_by = (
			frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
			or source.assessed_by
		)
		for row in target.hazards:
			score_hazard(row)

	return get_mapped_doc(
		DOCTYPE,
		source_name,
		{
			DOCTYPE: {
				"doctype": DOCTYPE,
				"validation": {"docstatus": ["=", 1], "status": ["=", ACTIVE]},
				"field_no_map": ["status", "superseded_by", "residual_risk_acceptance", "next_review_date"],
			},
			"Risk Assessment Hazard": {"doctype": "Risk Assessment Hazard"},
			"Risk Assessment Team Member": {"doctype": "Risk Assessment Team Member"},
			"Risk Assessment Action": {
				"doctype": "Risk Assessment Action",
				"condition": lambda row: not row.date_done,
			},
		},
		target_doc,
		postprocess,
	)


# Documents reviewed on a cycle, and the Employee field naming who leads the review.
REVIEWED = {DOCTYPE: ("assessed_by", "title"), "Job Hazard Analysis": ("prepared_by", "job_title")}


def assign_due_reviews():
	"""Daily: a ToDo on each approved risk assessment and JHA in force whose review is due, for
	the person who prepared it (or the Safety Managers when they have no user). One open ToDo
	per person per document."""
	fallback = None
	for doctype, (lead_field, title_field) in REVIEWED.items():
		due = frappe.get_all(
			doctype,
			filters={"docstatus": 1, "status": ACTIVE, "next_review_date": ["<=", today()]},
			fields=["name", f"{title_field} as title", f"{lead_field} as lead", "next_review_date"],
		)
		for doc in due:
			user = doc.lead and frappe.db.get_value("Employee", doc.lead, "user_id")
			if not user and fallback is None:
				fallback = role_users(REVIEW_FALLBACK_ROLE)
			assign(
				[user] if user else fallback,
				doctype,
				doc.name,
				_("Review {0} {1} (due {2}): use Start Review on the form.").format(
					_(doctype), doc.title, formatdate(doc.next_review_date)
				),
			)


def role_users(role: str) -> list[str]:
	users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
	return frappe.get_all(
		"User",
		filters=[
			["name", "in", users or [""]],
			["name", "not in", ["Administrator", "Guest"]],
			["enabled", "=", 1],
		],
		pluck="name",
	)
