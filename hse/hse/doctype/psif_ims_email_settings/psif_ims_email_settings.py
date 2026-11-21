# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class PSIFIMSEmailSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		acknowledgment_email: DF.Check
		assignment_emails: DF.Check
		certificate_reminder_email: DF.Check
		escalation_email: DF.Check
		monthly_email: DF.Check
		request_decision_email: DF.Check
		retraining_email: DF.Check
	# end: auto-generated types

	pass
