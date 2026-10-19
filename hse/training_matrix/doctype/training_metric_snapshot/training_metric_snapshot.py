# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class TrainingMetricSnapshot(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		avenue: DF.Data | None
		compliance_pct: DF.Percent
		compliant_items: DF.Int
		confirm_pending: DF.Int
		department: DF.Data | None
		due_items: DF.Int
		employees: DF.Int
		high_hazard_overdue: DF.Int
		overdue_items: DF.Int
		required_items: DF.Int
		snapshot_date: DF.Date
	# end: auto-generated types

	pass
