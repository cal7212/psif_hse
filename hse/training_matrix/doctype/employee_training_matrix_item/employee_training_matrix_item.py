# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class EmployeeTrainingMatrixItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		active: DF.Check
		applicability: DF.Literal["", "Applies", "Not Applicable"]
		assigned_on: DF.Date | None
		avenue: DF.Data | None
		company: DF.Link | None
		competency_evaluation: DF.Link | None
		completed_on: DF.Date | None
		course_title: DF.Data | None
		department: DF.Link | None
		development_due: DF.Date | None
		due_date: DF.Date | None
		employee: DF.Link | None
		employee_name: DF.Data | None
		evidence: DF.SmallText | None
		expires_on: DF.Date | None
		first_completed_on: DF.Date | None
		high_hazard: DF.Check
		in_progress: DF.Check
		is_required: DF.Check
		lms_reset_on: DF.Date | None
		needed_for: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		qualification: DF.Literal["Not Qualified", "Qualified"]
		requirement_code: DF.Literal["R", "C", "Dev", "—"]
		status: DF.Literal[
			"Not Started",
			"In Progress",
			"Due",
			"Overdue",
			"Completed",
			"Confirm Applicability",
			"Not Applicable",
		]
		training_record: DF.Link | None
		training_requirement: DF.Link
	# end: auto-generated types

	pass
