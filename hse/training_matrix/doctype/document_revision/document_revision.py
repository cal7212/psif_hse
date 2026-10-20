# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from hse.training_matrix.retraining import create_assignment

RETRAIN_NONE, READ_ACK = "No Retraining", "Read & Acknowledge"


class DocumentRevision(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hse.training_matrix.doctype.document_revision_course.document_revision_course import (
			DocumentRevisionCourse,
		)

		amended_from: DF.Link | None
		change_summary: DF.SmallText
		courses: DF.Table[DocumentRevisionCourse]
		document_number: DF.Data
		effective_date: DF.Date
		file_location: DF.Data | None
		previous_revision: DF.Data | None
		revision: DF.Data
	# end: auto-generated types

	def validate(self):
		self.document_number = (self.document_number or "").strip()
		if not self.previous_revision and self.courses:
			self.previous_revision = frappe.db.get_value(
				"Training Requirement", self.courses[0].training_requirement, "document_revision"
			)
		seen = set()
		for row in self.courses:
			if row.training_requirement in seen:
				frappe.throw(_("{0} is listed more than once.").format(frappe.bold(row.training_requirement)))
			seen.add(row.training_requirement)
			if row.retraining != RETRAIN_NONE and not row.due_date:
				frappe.throw(_("Row {0}: enter the retraining due date.").format(row.idx))
			if row.due_date and getdate(row.due_date) < getdate(self.effective_date):
				frappe.throw(_("Row {0}: the due date cannot be before the effective date.").format(row.idx))
			if row.retraining == READ_ACK and getdate(self.effective_date) > getdate(today()):
				frappe.throw(_("Read & Acknowledge retraining can be sent once the revision is effective."))

	def on_submit(self):
		for row in self.courses:
			frappe.db.set_value(
				"Training Requirement", row.training_requirement, "document_revision", self.revision
			)
			if row.retraining == RETRAIN_NONE:
				continue
			employees = trained_employees(row.training_requirement)
			if not employees:
				continue
			reason = _("{0} revised to Rev {1}: {2}").format(
				self.document_number, self.revision, self.change_summary
			)
			assignment = create_assignment(
				"Document Revision",
				employees,
				[row.training_requirement],
				self.effective_date,
				row.due_date,
				reason,
				reference_doctype=self.doctype,
				reference_name=self.name,
				delivery=row.retraining,
				notify=row.retraining != READ_ACK,  # the training record asks them to acknowledge instead
			)
			row.db_set("retraining_assignment", assignment)
			if row.retraining == READ_ACK:
				row.db_set("training_record", self.read_and_acknowledge(row, employees))

	def read_and_acknowledge(self, row, employees) -> str:
		"""A Read & Acknowledge training record: each employee acknowledges on My Training."""
		record = frappe.get_doc(
			{
				"doctype": "Training Record",
				"training_requirement": row.training_requirement,
				"training_date": self.effective_date,
				"source": "Read & Acknowledge",
				"document_number": self.document_number,
				"document_revision": self.revision,
				"document_section": row.document_section,
				"topics": self.change_summary,
				"attendees": [{"employee": e} for e in employees],
			}
		)
		record.flags.ignore_permissions = True
		record.insert()
		record.submit()
		return record.name

	def on_cancel(self):
		for row in self.courses:
			for doctype, name in (
				("Training Record", row.training_record),
				("Retraining Assignment", row.retraining_assignment),
			):
				if name and frappe.db.get_value(doctype, name, "docstatus") == 1:
					doc = frappe.get_doc(doctype, name)
					doc.flags.ignore_permissions = True
					doc.cancel()
			frappe.db.set_value(
				"Training Requirement", row.training_requirement, "document_revision", self.previous_revision
			)


def trained_employees(course: str) -> list[str]:
	"""Active employees who need the course and have training on record for it."""
	return sorted(
		set(
			frappe.get_all(
				"Employee Training Matrix Item",
				filters={
					"parenttype": "Employee Training Matrix",
					"training_requirement": course,
					"active": 1,
					"is_required": 1,
					"completed_on": ["is", "set"],
				},
				pluck="parent",
			)
		)
	)


@frappe.whitelist()
def get_courses(document_number: str) -> list[dict]:
	"""Courses trained on this document (including Safety Manual sections)."""
	return frappe.get_all(
		"Training Requirement",
		filters={"document_number": document_number, "disabled": 0},
		fields=["name as training_requirement", "course_title", "document_section"],
		order_by="name asc",
	)
