# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url, getdate

from hse.training_matrix.retraining import apply_retraining, can_assign


class RetrainingAssignment(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hse.training_matrix.doctype.retraining_assignment_course.retraining_assignment_course import (
			RetrainingAssignmentCourse,
		)
		from hse.training_matrix.doctype.retraining_assignment_employee.retraining_assignment_employee import (
			RetrainingAssignmentEmployee,
		)

		amended_from: DF.Link | None
		courses: DF.Table[RetrainingAssignmentCourse]
		delivery: DF.Literal["As Per Course", "Read & Acknowledge", "Instructor-led"]
		due_date: DF.Date
		effective_date: DF.Date
		employees: DF.Table[RetrainingAssignmentEmployee]
		reason: DF.SmallText
		reason_type: DF.Literal[
			"Incident or Near Miss",
			"Nonconformance or CAPA",
			"Audit Finding",
			"Document Revision",
			"Return from Absence",
			"Manager Observation",
			"Other",
		]
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
	# end: auto-generated types

	def validate(self):
		if getdate(self.due_date) < getdate(self.effective_date):
			frappe.throw(_("Retraining Due cannot be before Effective From."))
		if self.reference_doctype and not self.reference_name:
			frappe.throw(_("Select the {0} this retraining comes from.").format(self.reference_doctype))
		for table, field in (("employees", "employee"), ("courses", "training_requirement")):
			seen = set()
			for row in self.get(table):
				if row.get(field) in seen:
					frappe.throw(_("{0} is listed more than once.").format(frappe.bold(row.get(field))))
				seen.add(row.get(field))
		if not self.flags.ignore_permissions:
			for row in self.employees:
				if not can_assign(row.employee):
					frappe.throw(
						_("You can only assign retraining to your own team: {0}.").format(
							row.employee_name or row.employee
						),
						frappe.PermissionError,
					)

	def on_submit(self):
		for row in self.employees:
			apply_retraining(row.employee)
		if not self.flags.skip_notify:
			self.notify_employees()

	def on_cancel(self):
		for row in self.employees:
			apply_retraining(row.employee)

	def notify_employees(self):
		users = [frappe.db.get_value("Employee", r.employee, "user_id") for r in self.employees]
		users = [u for u in users if u]
		if not users:
			return
		courses = ", ".join(f"{c.training_requirement} {c.course_title or ''}".strip() for c in self.courses)
		frappe.sendmail(
			recipients=users,
			subject=_("Retraining required: {0}").format(courses),
			message=_(
				"<p>You need to retrain on <b>{0}</b> by {1}.</p><p>Reason: {2}</p>"
				"<p>See <a href='{3}'>My Training</a> and speak to your manager to arrange it.</p>"
			).format(
				frappe.utils.escape_html(courses),
				frappe.format(self.due_date, "Date"),
				frappe.utils.escape_html(self.reason or ""),
				get_url("/my-training"),
			),
			reference_doctype=self.doctype,
			reference_name=self.name,
		)
