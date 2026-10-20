# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url, getdate, today

from hse.training_matrix import status as st
from hse.training_matrix.evidence import QUIZ_METHODS, QUIZ_PASS_MARK, acknowledgment_required, recalculate
from hse.training_matrix.trainers import check_authorized

TRAINER_LED = {"Classroom", "OJT"}


class TrainingRecord(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hse.training_matrix.doctype.training_record_attendee.training_record_attendee import (
			TrainingRecordAttendee,
		)

		amended_from: DF.Link | None
		attendees: DF.Table[TrainingRecordAttendee]
		avenue: DF.Data | None
		course_title: DF.Data | None
		document_number: DF.Data | None
		document_revision: DF.Data | None
		document_section: DF.Data | None
		duration_minutes: DF.Int
		external_provider: DF.Data | None
		imported_from: DF.Data | None
		lms_course: DF.Data | None
		source: DF.Literal["Classroom", "OJT", "Read & Acknowledge", "LMS Course", "External Certificate"]
		status: DF.Literal["Draft", "Awaiting Acknowledgment", "Complete", "Cancelled"]
		topics: DF.SmallText | None
		trainer: DF.Link | None
		trainer_name: DF.Data | None
		training_date: DF.Date
		training_requirement: DF.Link
		verification_method: DF.Data | None
	# end: auto-generated types

	def validate(self):
		if getdate(self.training_date) > getdate(today()):
			frappe.throw(_("Training Date cannot be in the future."))
		req = frappe.get_cached_doc("Training Requirement", self.training_requirement)
		self.validate_attendees()
		self.validate_trainer(req)
		self.validate_certificates(req)
		self.set_results(req)
		self.status = self.get_status()

	def validate_attendees(self):
		seen = set()
		for row in self.attendees:
			if row.employee in seen:
				frappe.throw(
					_("Row {0}: {1} is listed more than once.").format(
						row.idx, row.employee_name or row.employee
					)
				)
			seen.add(row.employee)
			if self.trainer and row.employee == self.trainer:
				frappe.throw(_("Row {0}: the trainer cannot also be an attendee.").format(row.idx))

	def validate_trainer(self, req):
		if self.source not in TRAINER_LED:
			return
		if not (self.trainer or self.external_provider):
			frappe.throw(
				_("Enter the Trainer, or the External Provider for training delivered by an outside company.")
			)
		if self.trainer and req.requires_qualified_trainer:
			check_authorized(self.trainer, self.training_requirement, _("The trainer"))

	def validate_certificates(self, req):
		if self.source != "External Certificate":
			return
		for row in self.attendees:
			if not row.certificate:
				frappe.throw(_("Row {0}: attach the certificate.").format(row.idx))
			if req.refresher_frequency == st.PER_CERTIFICATION and not row.expires_on:
				frappe.throw(_("Row {0}: enter the certificate expiry date.").format(row.idx))

	def set_results(self, req):
		"""Quiz-verified courses pass at 80%; a submitted record with no result means attended."""
		for row in self.attendees:
			if not row.result and row.score and req.verification_method in QUIZ_METHODS:
				row.result = "Pass" if row.score >= QUIZ_PASS_MARK else "Fail"
			if self.docstatus == 1 and not row.result:
				row.result = "Pass"

	def get_status(self) -> str:
		if self.docstatus == 2:
			return "Cancelled"
		if self.docstatus == 0:
			return "Draft"
		if acknowledgment_required(self.source) and any(
			not r.acknowledged and r.result != "Fail" for r in self.attendees
		):
			return "Awaiting Acknowledgment"
		return "Complete"

	def on_submit(self):
		self.db_set("status", self.get_status(), update_modified=False)
		if acknowledgment_required(self.source):
			self.request_acknowledgments()
		for row in self.attendees:
			recalculate(row.employee, self.training_requirement)

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)
		for row in self.attendees:
			recalculate(row.employee, self.training_requirement)

	def request_acknowledgments(self):
		recipients = [
			r.user_id for r in self.attendees if r.user_id and not r.acknowledged and r.result != "Fail"
		]
		if not recipients:
			return
		frappe.sendmail(
			recipients=recipients,
			subject=_("Please acknowledge your training: {0}").format(
				self.course_title or self.training_requirement
			),
			message=_(
				"<p>You attended <b>{0}</b> on {1}.</p><p>Please confirm your attendance and understanding in"
				" <a href='{2}'>My Training</a>. The training does not count until you do (TRN-700).</p>"
			).format(
				frappe.utils.escape_html(self.course_title or self.training_requirement),
				frappe.format(self.training_date, "Date"),
				get_url("/my-training"),
			),
			reference_doctype=self.doctype,
			reference_name=self.name,
		)
