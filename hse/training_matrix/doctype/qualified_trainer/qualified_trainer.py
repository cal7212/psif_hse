# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from hse.training_matrix.trainers import own_qualification, suspension_reason, sync_role


class QualifiedTrainer(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hse.training_matrix.doctype.qualified_trainer_course.qualified_trainer_course import (
			QualifiedTrainerCourse,
		)

		active_courses: DF.Int
		courses: DF.Table[QualifiedTrainerCourse]
		disabled: DF.Check
		employee: DF.Link
		employee_name: DF.Data | None
		user_id: DF.Link | None
	# end: auto-generated types

	def validate(self):
		seen = set()
		for row in self.courses:
			if row.training_requirement in seen:
				frappe.throw(
					_("Row {0}: {1} is listed more than once.").format(row.idx, row.training_requirement)
				)
			seen.add(row.training_requirement)
			if self.user_id and row.designated_by == self.user_id:
				frappe.throw(
					_("Row {0}: a trainer cannot designate themselves (TRN-700 §4.8).").format(row.idx)
				)
		self.check_new_courses()
		if not self.flags.from_refresh:
			self.apply_status(today())

	def check_new_courses(self):
		"""A trainer must be Qualified in a course before being designated for it."""
		before = self.get_doc_before_save()
		existing = {r.training_requirement for r in before.courses} if before else set()
		qualified = own_qualification(self.employee)
		for row in self.courses:
			if (
				row.training_requirement not in existing
				and qualified.get(row.training_requirement) != "Qualified"
			):
				frappe.throw(
					_("Row {0}: {1} must be Qualified in {2} on their own training matrix first.").format(
						row.idx, self.employee_name, frappe.bold(row.training_requirement)
					)
				)

	def apply_status(self, on_date):
		qualified = own_qualification(self.employee)
		for row in self.courses:
			reason = suspension_reason(row, qualified, on_date)
			row.status = "Suspended" if reason else "Active"
			row.suspension_reason = reason
		self.active_courses = 0 if self.disabled else sum(1 for r in self.courses if r.status == "Active")

	def on_update(self):
		sync_role(self.user_id, bool(self.active_courses))

	def on_trash(self):
		sync_role(self.user_id, False)
