# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class EmployeeTrainingMatrixSkill(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		authorization_expires: DF.Date | None
		authorized_on: DF.Date | None
		courses_qualified: DF.Int
		courses_required: DF.Int
		eligible_since: DF.Date | None
		missing: DF.SmallText | None
		needed_for: DF.Literal["Role", "Target", "Prerequisite"]
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		progress: DF.Data | None
		skill: DF.Link
		skill_authorization: DF.Link | None
		status: DF.Literal["Not Started", "In Training", "Ready for Authorization", "Authorized", "Lapsed"]
		target_due: DF.Date | None
	# end: auto-generated types

	pass
