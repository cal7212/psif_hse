# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from hse.training_matrix.matrix import enqueue_resync


class TrainingRole(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hse.training_matrix.doctype.training_role_department.training_role_department import (
			TrainingRoleDepartment,
		)
		from hse.training_matrix.doctype.training_role_designation.training_role_designation import (
			TrainingRoleDesignation,
		)
		from hse.training_matrix.doctype.training_role_employee_group.training_role_employee_group import (
			TrainingRoleEmployeeGroup,
		)

		departments: DF.TableMultiSelect[TrainingRoleDepartment]
		description: DF.SmallText | None
		designations: DF.TableMultiSelect[TrainingRoleDesignation]
		disabled: DF.Check
		employee_groups: DF.TableMultiSelect[TrainingRoleEmployeeGroup]
		role_name: DF.Data
	# end: auto-generated types

	def validate(self):
		for table, field in (
			("designations", "designation"),
			("departments", "department"),
			("employee_groups", "employee_group"),
		):
			seen = set()
			for row in self.get(table):
				if row.get(field) in seen:
					frappe.throw(_("{0} is listed more than once.").format(frappe.bold(row.get(field))))
				seen.add(row.get(field))

	def on_update(self):
		if not self.flags.skip_resync:
			enqueue_resync()
