# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, cint

from hse.training_matrix import status as st
from hse.training_matrix.matrix import enqueue_resync

MATERIALS_REVIEW_MONTHS = 24  # TRN-700 §4.14


class TrainingRequirement(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hse.training_matrix.doctype.training_requirement_role.training_requirement_role import (
			TrainingRequirementRole,
		)

		all_employees: DF.Check
		avenue: DF.Literal["HR Onboarding", "Safety / EHS", "QMS", "Technical"]
		course_id: DF.Data
		course_title: DF.Data
		delivery_method: DF.Data | None
		disabled: DF.Check
		document_number: DF.Data | None
		document_revision: DF.Data | None
		document_section: DF.Data | None
		duration_minutes: DF.Int
		frequency_notes: DF.Data | None
		frequency_summary: DF.Data | None
		high_hazard: DF.Check
		initial_due_basis: DF.Literal["Date of Hire", "Date Assigned"]
		initial_due_days: DF.Int
		materials_review_due: DF.Date | None
		materials_reviewed_on: DF.Date | None
		refresher_frequency: DF.Literal[
			"One-time", "Annually", "Every 2 Years", "Every 3 Years", "Per Certification"
		]
		requires_qualified_trainer: DF.Check
		retrain_on_revision: DF.Check
		roles: DF.Table[TrainingRequirementRole]
		verification_method: DF.Literal[
			"",
			"Quiz (80%)",
			"LMS Acknowledgment",
			"LMS Attendance Record",
			"LMS Completion Record",
			"Practical Demonstration",
			"Practical Evaluation",
			"Test and Practical",
			"Supervisor Observation",
			"Valid Certificate",
			"Quiz and MVR Review",
			"Certificate and Observed Audit",
			"TRN-704 Checklist",
			"Respirator Fit Test",
		]
	# end: auto-generated types

	def validate(self):
		self.document_number = self.document_number or self.course_id
		self.frequency_summary = st.frequency_summary(
			self.initial_due_basis,
			self.initial_due_days,
			self.refresher_frequency,
			self.retrain_on_revision,
			self.frequency_notes,
		)
		self.materials_review_due = (
			add_months(self.materials_reviewed_on, MATERIALS_REVIEW_MONTHS)
			if self.materials_reviewed_on
			else None
		)
		if cint(self.initial_due_days) < 0:
			frappe.throw(_("Days Allowed cannot be negative."))
		seen = set()
		for row in self.roles:
			if row.training_role in seen:
				frappe.throw(
					_("Row {0}: {1} is listed more than once.").format(
						row.idx, frappe.bold(row.training_role)
					)
				)
			seen.add(row.training_role)

	def on_update(self):
		if not self.flags.skip_resync:
			enqueue_resync()

	def after_rename(self, old, new, merge=False):
		frappe.db.set_value("Training Requirement", new, "course_id", new, update_modified=False)
