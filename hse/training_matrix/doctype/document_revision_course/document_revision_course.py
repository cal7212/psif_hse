# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class DocumentRevisionCourse(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		course_title: DF.Data | None
		document_section: DF.Data | None
		due_date: DF.Date | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		retraining: DF.Literal["No Retraining", "Read & Acknowledge", "Instructor-led"]
		retraining_assignment: DF.Link | None
		training_record: DF.Link | None
		training_requirement: DF.Link
	# end: auto-generated types

	pass
