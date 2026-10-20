# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class TrainingRecordAttendee(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		acknowledged: DF.Check
		acknowledged_on: DF.Datetime | None
		certificate: DF.Attach | None
		employee: DF.Link
		employee_name: DF.Data | None
		expires_on: DF.Date | None
		lms_enrollment: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		result: DF.Literal["", "Pass", "Fail"]
		score: DF.Percent
		user_id: DF.Link | None
	# end: auto-generated types

	pass
