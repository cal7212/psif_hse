# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from hse.training_matrix import skill_status as ss
from hse.training_matrix.matrix import sync_matrix
from hse.training_matrix.skills import authorization_expiry

# Besides the employee's own manager (Reports To), these roles may authorize skills.
AUTHORIZER_ROLES = ("System Manager", "HR Manager")


class SkillAuthorization(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		authorization_date: DF.Date
		authorized_by: DF.Link | None
		authorizer_name: DF.Data | None
		comments: DF.SmallText | None
		employee: DF.Link
		employee_name: DF.Data | None
		expires_on: DF.Date | None
		scope: DF.SmallText | None
		skill: DF.Link
	# end: auto-generated types

	def before_insert(self):
		self.authorized_by = frappe.session.user

	def validate(self):
		if getdate(self.authorization_date) > getdate(today()):
			frappe.throw(_("Authorization Date cannot be in the future."))
		if not self.expires_on:
			self.expires_on = authorization_expiry(self.skill, self.authorization_date)
		self.validate_authorizer()

	def validate_authorizer(self):
		user = self.authorized_by or frappe.session.user
		if frappe.db.get_value("Employee", self.employee, "user_id") == user:
			frappe.throw(_("You cannot authorize your own skills."), frappe.PermissionError)
		if set(frappe.get_roles(user)) & set(AUTHORIZER_ROLES):
			return
		manager = frappe.db.get_value("Employee", self.employee, "reports_to")
		if not manager or frappe.db.get_value("Employee", manager, "user_id") != user:
			frappe.throw(
				_("Only {0}'s manager (Reports To) or an HR Manager can authorize skills.").format(
					self.employee_name
				),
				frappe.PermissionError,
			)

	def before_submit(self):
		"""The courses and prerequisites must be Qualified now: no early sign-off."""
		row = frappe.db.get_value(
			"Employee Training Matrix Skill",
			{"parent": self.employee, "parenttype": "Employee Training Matrix", "skill": self.skill},
			["status", "eligible_since", "missing"],
			as_dict=True,
		)
		if not row or row.status not in (ss.READY, ss.AUTHORIZED):
			frappe.throw(
				_("{0} is not ready for authorization as {1}. Still needed: {2}").format(
					self.employee_name,
					frappe.bold(self.skill),
					(row and row.missing) or _("the skill's courses"),
				),
				title=_("Not Ready"),
			)
		if row.eligible_since and getdate(self.authorization_date) < getdate(row.eligible_since):
			frappe.throw(
				_("Authorization Date cannot be before the employee became eligible ({0}).").format(
					frappe.format(row.eligible_since, "Date")
				)
			)

	def on_submit(self):
		sync_matrix(self.employee)

	def on_cancel(self):
		sync_matrix(self.employee)
