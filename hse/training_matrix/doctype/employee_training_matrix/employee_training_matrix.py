# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

from hse.training_matrix import lms, skills
from hse.training_matrix import status as st
from hse.training_matrix.matrix import apply_status


class EmployeeTrainingMatrix(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hse.training_matrix.doctype.employee_target_skill.employee_target_skill import (
			EmployeeTargetSkill,
		)
		from hse.training_matrix.doctype.employee_training_matrix_item.employee_training_matrix_item import (
			EmployeeTrainingMatrixItem,
		)
		from hse.training_matrix.doctype.employee_training_matrix_role.employee_training_matrix_role import (
			EmployeeTrainingMatrixRole,
		)
		from hse.training_matrix.doctype.employee_training_matrix_skill.employee_training_matrix_skill import (
			EmployeeTrainingMatrixSkill,
		)

		active: DF.Check
		company: DF.Link | None
		compliant_count: DF.Int
		confirm_count: DF.Int
		date_of_joining: DF.Date | None
		department: DF.Link | None
		designation: DF.Link | None
		due_count: DF.Int
		employee: DF.Link
		employee_name: DF.Data | None
		items: DF.Table[EmployeeTrainingMatrixItem]
		last_refreshed: DF.Datetime | None
		no_lms_login: DF.Check
		overdue_count: DF.Int
		percent_complete: DF.Percent
		required_count: DF.Int
		roles: DF.TableMultiSelect[EmployeeTrainingMatrixRole]
		roles_from_hr: DF.Check
		skills: DF.Table[EmployeeTrainingMatrixSkill]
		target_skills: DF.Table[EmployeeTargetSkill]
		user_id: DF.Link | None
	# end: auto-generated types

	def validate(self):
		on_date = getdate(self.flags.on_date or today())
		for row in self.items:
			if row.completed_on and getdate(row.completed_on) > on_date:
				frappe.throw(_("Row {0}: Completed On cannot be in the future.").format(row.idx))
			if row.completed_on and row.expires_on and getdate(row.expires_on) < getdate(row.completed_on):
				frappe.throw(
					_("Row {0}: the certificate cannot expire before it was completed.").format(row.idx)
				)
		self.check_certificates()
		apply_status(self, on_date=on_date)

	def check_certificates(self):
		"""Per Certification courses need an expiry date once completed (TRN-700 §4.4)."""
		names = {
			r.training_requirement
			for r in self.items
			if r.completed_on and not r.expires_on and not (r.training_record or r.competency_evaluation)
		}
		if not names:
			return
		per_cert = set(
			frappe.get_all(
				"Training Requirement",
				filters={"name": ["in", list(names)], "refresher_frequency": st.PER_CERTIFICATION},
				pluck="name",
			)
		)
		for row in self.items:
			if (
				row.training_requirement in per_cert
				and row.completed_on
				and not row.expires_on
				and not row.training_record
			):
				frappe.throw(
					_("Row {0}: enter the certificate expiry date for {1}.").format(
						row.idx, frappe.bold(row.training_requirement)
					)
				)

	def on_update(self):
		skills.after_matrix_update(self)
		if not self.flags.skip_lms:
			lms.enroll_required(self)
