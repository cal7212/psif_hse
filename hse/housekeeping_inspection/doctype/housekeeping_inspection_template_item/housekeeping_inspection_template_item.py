# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class HousekeepingInspectionTemplateItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		category: DF.Literal["", "Walking-Working Surfaces", "Aisles and Exits", "Fire Protection", "Electrical", "Material Storage", "Chemicals and Flammables", "Waste and Sanitation", "Tools and Equipment", "General"]
		check_item: DF.Data
		criteria: DF.SmallText | None
		is_critical: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		reference: DF.Data | None
	# end: auto-generated types

	pass
