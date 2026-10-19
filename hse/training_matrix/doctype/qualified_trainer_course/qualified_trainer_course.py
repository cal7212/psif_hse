# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class QualifiedTrainerCourse(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		basis: DF.SmallText | None
		certification: DF.Data | None
		certification_expires: DF.Date | None
		course_title: DF.Data | None
		designated_by: DF.Link
		designated_on: DF.Date
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		status: DF.Literal["Active", "Suspended"]
		suspension_reason: DF.Data | None
		training_requirement: DF.Link
	# end: auto-generated types

	pass
