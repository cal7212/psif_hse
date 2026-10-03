# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class QCStage(Document):
	def validate(self):
		if self.sequence is None or self.sequence < 0:
			frappe.throw(_("Sequence must be zero or greater."))
		if self.is_final_release:
			self.is_required = 1
			if not self.disabled:
				self.validate_single_final_release()

	def validate_single_final_release(self):
		"""One final release stage per shop and job type."""
		others = frappe.get_all(
			"QC Stage",
			filters={"is_final_release": 1, "disabled": 0, "name": ("!=", self.name)},
			fields=["name", "shop", "job_type"],
		)
		mine = {"Both": {"New Build", "Repair"}}.get(self.job_type, {self.job_type})
		for o in others:
			theirs = {"Both": {"New Build", "Repair"}}.get(o.job_type, {o.job_type})
			same_shop = (o.shop or None) == (self.shop or None)
			if same_shop and mine & theirs:
				frappe.throw(
					_("{0} is already the Final Release stage for {1} {2}.").format(
						frappe.bold(o.name), self.shop or _("all shops"), self.job_type
					)
				)
