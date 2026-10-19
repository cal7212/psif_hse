# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class CompetencyChecklistTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hse.training_matrix.doctype.competency_checklist_template_item.competency_checklist_template_item import (
			CompetencyChecklistTemplateItem,
		)

		disabled: DF.Check
		items: DF.Table[CompetencyChecklistTemplateItem]
		template_name: DF.Data
		training_requirement: DF.Link
	# end: auto-generated types

	pass
