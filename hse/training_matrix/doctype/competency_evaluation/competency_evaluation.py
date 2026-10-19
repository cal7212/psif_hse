# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.form.assign_to import add as assign
from frappe.model.document import Document
from frappe.utils import getdate, today

from hse.training_matrix.evidence import recalculate
from hse.training_matrix.trainers import check_authorized, is_authorized


class CompetencyEvaluation(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hse.training_matrix.doctype.competency_evaluation_item.competency_evaluation_item import (
			CompetencyEvaluationItem,
		)

		amended_from: DF.Link | None
		basis: DF.Literal["Training", "Prior Experience"]
		checklist: DF.Table[CompetencyEvaluationItem]
		checklist_template: DF.Link | None
		comments: DF.SmallText | None
		course_title: DF.Data | None
		employee: DF.Link
		employee_name: DF.Data | None
		evaluation_date: DF.Date
		evaluator: DF.Link
		evaluator_name: DF.Data | None
		evidence: DF.Attach | None
		result: DF.Literal["", "Pass", "Fail"]
		training_record: DF.Link | None
		training_requirement: DF.Link
	# end: auto-generated types

	def validate(self):
		if getdate(self.evaluation_date) > getdate(today()):
			frappe.throw(_("Evaluation Date cannot be in the future."))
		if self.evaluator == self.employee:
			frappe.throw(_("An employee cannot evaluate their own competency."))
		if self.basis == "Prior Experience" and not self.evidence:
			frappe.throw(_("Attach the evidence of prior experience (TRN-700 §4.8)."))
		if self.basis != "Training":
			self.training_record = None
		self.validate_training_record()
		self.validate_evaluator()
		self.set_result()

	def validate_training_record(self):
		if not self.training_record:
			return
		record = frappe.db.get_value(
			"Training Record", self.training_record, ["training_requirement", "docstatus"], as_dict=True
		)
		if record.training_requirement != self.training_requirement or record.docstatus != 1:
			frappe.throw(_("The Training Record must be a submitted record for the same course."))
		if not frappe.db.exists(
			"Training Record Attendee", {"parent": self.training_record, "employee": self.employee}
		):
			frappe.throw(_("{0} is not an attendee on {1}.").format(self.employee_name, self.training_record))

	def validate_evaluator(self):
		if frappe.db.get_value(
			"Training Requirement", self.training_requirement, "requires_qualified_trainer"
		):
			check_authorized(self.evaluator, self.training_requirement, _("The evaluator"))
		elif not is_authorized(self.evaluator, self.training_requirement):
			frappe.msgprint(
				_("{0} is not on the Qualified Trainer register for {1}.").format(
					self.evaluator_name or self.evaluator, self.training_requirement
				),
				indicator="orange",
				alert=True,
			)

	def set_result(self):
		results = [r.result for r in self.checklist]
		if "Fail" in results:
			self.result = "Fail"
		if self.docstatus == 1 and not self.result:
			if results and all(r in ("Pass", "N/A") for r in results):
				self.result = "Pass"
			else:
				frappe.throw(_("Enter the overall Result, or a result for every checklist item."))

	def on_submit(self):
		recalculate(self.employee, self.training_requirement)
		if self.result == "Fail":
			self.assign_retraining()

	def on_cancel(self):
		recalculate(self.employee, self.training_requirement)

	def assign_retraining(self):
		"""Failed evaluation: the employee's manager arranges retraining (TRN-700 §4.8)."""
		manager = frappe.db.get_value("Employee", self.employee, "reports_to")
		users = [frappe.db.get_value("Employee", manager, "user_id")] if manager else []
		users = [u for u in users if u] or frappe.get_all(
			"Has Role", filters={"role": "Training Coordinator", "parenttype": "User"}, pluck="parent"
		)
		if users:
			assign(
				{
					"assign_to": list(dict.fromkeys(users)),
					"doctype": self.doctype,
					"name": self.name,
					"description": _("{0} did not pass {1}. Arrange retraining and re-evaluation.").format(
						self.employee_name, self.training_requirement
					),
				}
			)


@frappe.whitelist()
def get_checklist(template: str) -> list[dict]:
	frappe.has_permission("Competency Checklist Template", "read", template, throw=True)
	return frappe.get_all(
		"Competency Checklist Template Item",
		filters={"parent": template, "parenttype": "Competency Checklist Template"},
		fields=["item", "criteria"],
		order_by="idx asc",
	)
