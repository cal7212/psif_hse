# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TrainingMatrixSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hse.training_matrix.doctype.training_matrix_settings_role.training_matrix_settings_role import (
			TrainingMatrixSettingsRole,
		)
		from hse.training_matrix.doctype.training_matrix_settings_user.training_matrix_settings_user import (
			TrainingMatrixSettingsUser,
		)

		absence_days: DF.Int
		absence_due_days: DF.Int
		certificate_business_days: DF.Int
		escalation_days: DF.Int
		escalation_roles: DF.TableMultiSelect[TrainingMatrixSettingsRole]
		escalation_users: DF.TableMultiSelect[TrainingMatrixSettingsUser]
		monthly_email: DF.Check
		report_roles: DF.TableMultiSelect[TrainingMatrixSettingsRole]
		report_users: DF.TableMultiSelect[TrainingMatrixSettingsUser]
	# end: auto-generated types

	def validate(self):
		if (self.escalation_days or 0) < 1:
			frappe.throw(_("Escalate After must be at least 1 day."))
		if (self.absence_days or 0) < 1:
			frappe.throw(_("The absence threshold must be at least 1 day."))
