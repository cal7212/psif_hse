# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

PRIVILEGED = ("System Manager", "HR Manager", "Training Coordinator")


class TrainingRequest(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		certificate_due: DF.Date | None
		certificate_reminded_on: DF.Date | None
		completed_on: DF.Date | None
		decided_by: DF.Link | None
		decided_on: DF.Date | None
		decision_notes: DF.SmallText | None
		employee: DF.Link
		employee_name: DF.Data | None
		estimated_cost: DF.Currency | None
		preferred_date: DF.Date | None
		provider: DF.Data | None
		reason: DF.SmallText
		request_type: DF.Literal["Internal Course", "External Training"]
		status: DF.Literal["Pending", "Approved", "Rejected", "Completed", "Cancelled"]
		training_record: DF.Link | None
		training_requirement: DF.Link | None
		training_title: DF.Data
	# end: auto-generated types

	def validate(self):
		if self.training_requirement and not self.training_title:
			self.training_title = frappe.db.get_value(
				"Training Requirement", self.training_requirement, "course_title"
			)
		if self.request_type != "External Training":
			self.provider = self.provider or None

	def before_insert(self):
		"""Employees request training for themselves; HR and the Training Coordinator for anyone."""
		if self.flags.ignore_permissions or set(frappe.get_roles()) & set(PRIVILEGED):
			return
		own = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		if self.employee != own:
			frappe.throw(_("You can only request training for yourself."), frappe.PermissionError)
		self.status = "Pending"
