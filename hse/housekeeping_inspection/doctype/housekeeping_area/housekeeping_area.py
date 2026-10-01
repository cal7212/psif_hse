# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today

from hse.housekeeping_inspection.utils import AS_NEEDED, AWAITING_RETURN, NOT_SCHEDULED, schedule_status_for


class HousekeepingArea(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		area_name: DF.Data
		area_owner: DF.Link | None
		area_owner_name: DF.Data | None
		company: DF.Link
		department: DF.Link | None
		disabled: DF.Check
		housekeeping_status: DF.Literal["Satisfactory", "Action Required", "Hazard Open"]
		inspector: DF.Link | None
		inspector_name: DF.Data | None
		inspector_user: DF.Link | None
		last_inspection: DF.Link | None
		last_inspection_date: DF.Date | None
		last_score: DF.Percent
		location: DF.Link | None
		next_due_date: DF.Date | None
		periodicity: DF.Literal["Daily", "Weekly", "Monthly", "Quarterly", "As Needed"]
		post_return_template: DF.Link | None
		schedule_status: DF.Literal["Current", "Due", "Overdue", "Not Scheduled", "Awaiting Return"]
		template: DF.Link
	# end: auto-generated types

	def validate(self):
		if frappe.db.get_value("Housekeeping Inspection Template", self.template, "disabled"):
			frappe.throw(_("Inspection Template {0} is disabled.").format(frappe.bold(self.template)))
		if self.periodicity == AS_NEEDED:
			self.next_due_date = None
			if self.schedule_status != AWAITING_RETURN:
				self.schedule_status = NOT_SCHEDULED
			return
		self.post_return_template = None
		if not self.next_due_date:
			self.next_due_date = today()
		self.schedule_status = schedule_status_for(self.next_due_date)
