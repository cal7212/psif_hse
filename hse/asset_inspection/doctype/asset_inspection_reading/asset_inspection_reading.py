# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class AssetInspectionReading(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		check_item: DF.Data | None
		criteria: DF.SmallText | None
		finding: DF.SmallText | None
		is_critical: DF.Check
		max_value: DF.Float
		min_value: DF.Float
		numeric: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		photo: DF.AttachImage | None
		reading_value: DF.Float
		result: DF.Literal["", "Pass", "Fail", "N/A"]
		uom: DF.Link | None
	# end: auto-generated types

	pass
