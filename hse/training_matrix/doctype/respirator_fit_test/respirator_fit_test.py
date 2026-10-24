# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Respirator fit test record (OSHA 1910.134(f) and (m)(2)).

A submitted test is the evidence for every Training Requirement verified by "Respirator Fit Test",
which in turn is a course of the Respirator Wearer skill: the employee becomes ready for
authorization only with a current passed fit test and current respirator training.

An in-house tester must hold the Respirator Fit Tester skill, authorized and current, when the test
is submitted. A test run by an outside provider names the provider instead.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, getdate, today

from hse.training_matrix.evidence import recalculate_fit_test_courses
from hse.training_matrix.setup.respirator import TESTER_SKILL
from hse.training_matrix.skill_status import AUTHORIZED

QLFT, QNFT = "Qualitative (QLFT)", "Quantitative (QNFT)"
# OSHA 1910.134 Appendix A accepted protocols, by test type.
PROTOCOLS = {
	QLFT: ("Isoamyl Acetate (banana oil)", "Saccharin", "Bitrex", "Irritant Smoke"),
	QNFT: (
		"Generated Aerosol",
		"Ambient Aerosol CNC (standard)",
		"Modified Ambient Aerosol CNC",
		"Controlled Negative Pressure (CNP)",
		"CNP REDON",
	),
}
RETEST_MONTHS = 12  # 1910.134(f)(2): at least annually


class RespiratorFitTest(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		comments: DF.SmallText | None
		employee: DF.Link
		employee_name: DF.Data | None
		fit_factor: DF.Float
		instrument: DF.Link | None
		manufacturer: DF.Data
		medical_clearance_date: DF.Date
		medical_limitations: DF.SmallText | None
		model: DF.Data
		next_due_date: DF.Date | None
		protocol: DF.Literal[
			"",
			"Isoamyl Acetate (banana oil)",
			"Saccharin",
			"Bitrex",
			"Irritant Smoke",
			"Generated Aerosol",
			"Ambient Aerosol CNC (standard)",
			"Modified Ambient Aerosol CNC",
			"Controlled Negative Pressure (CNP)",
			"CNP REDON",
		]
		provider: DF.Data | None
		respirator_item: DF.Link | None
		result: DF.Literal["", "Pass", "Fail"]
		size: DF.Data
		style: DF.Literal[
			"",
			"Filtering Facepiece (e.g. N95)",
			"Elastomeric Half Mask",
			"Elastomeric Full Facepiece",
			"Tight-Fitting PAPR",
			"Tight-Fitting Supplied Air / SCBA",
		]
		test_date: DF.Date
		test_record: DF.Attach | None
		test_type: DF.Literal["", "Qualitative (QLFT)", "Quantitative (QNFT)"]
		tester: DF.Link | None
		tester_name: DF.Data
		written_recommendation: DF.Check
	# end: auto-generated types

	def validate(self):
		if getdate(self.test_date) > getdate(today()):
			frappe.throw(_("Test Date cannot be in the future."))
		if self.tester and self.tester == self.employee:
			frappe.throw(_("An employee cannot fit test themselves."))
		if self.protocol and self.protocol not in PROTOCOLS.get(self.test_type, ()):
			frappe.throw(
				_("{0} is not a {1} protocol.").format(
					frappe.bold(self.protocol), self.test_type or _("fit test")
				)
			)
		if self.test_type != QNFT:
			self.fit_factor = 0
			self.instrument = None
		if self.medical_clearance_date and getdate(self.medical_clearance_date) > getdate(self.test_date):
			frappe.throw(_("The medical clearance must be on or before the Test Date (OSHA 1910.134(e)(1))."))
		self.next_due_date = add_months(self.test_date, RETEST_MONTHS)

	def before_submit(self):
		self.check_tester()
		missing = []
		if not self.written_recommendation:
			missing.append(_("confirm the PLHCP written recommendation is on file"))
		if self.test_type == QNFT and not self.fit_factor:
			missing.append(_("enter the overall fit factor"))
		if self.test_type == QNFT and not self.test_record:
			missing.append(_("attach the test record or printout"))
		if missing:
			frappe.throw(_("Before submitting: {0}.").format("; ".join(missing)), title=_("Incomplete"))

	def check_tester(self):
		if not self.tester:
			if not (self.provider or "").strip():
				frappe.throw(
					_("Select the Tester (Employee), or enter the Outside Provider for an outside fit test."),
					title=_("Tester Required"),
				)
			return
		if not tester_is_qualified(self.tester):
			frappe.throw(
				_(
					"{0} does not hold the {1} skill. An in-house tester needs it authorized and current; "
					"see their Employee Training Matrix."
				).format(frappe.bold(self.tester_name or self.tester), frappe.bold(TESTER_SKILL)),
				title=_("Tester Not Qualified"),
			)

	def on_submit(self):
		recalculate_fit_test_courses(self.employee)

	def on_cancel(self):
		recalculate_fit_test_courses(self.employee)


def tester_is_qualified(employee: str) -> bool:
	"""Authorized and current on the tester's matrix (lapses and expiries already applied)."""
	return bool(
		frappe.db.exists(
			"Employee Training Matrix Skill",
			{
				"parenttype": "Employee Training Matrix",
				"parent": employee,
				"skill": TESTER_SKILL,
				"status": AUTHORIZED,
			},
		)
	)


@frappe.whitelist()
def item_details(item: str) -> dict:
	"""Make and model from a respirator Item, to prefill the test."""
	frappe.has_permission("Item", "read", item, throw=True)
	row = frappe.db.get_value("Item", item, ["item_name", "brand", "description"], as_dict=True) or {}
	return {"manufacturer": row.get("brand"), "model": row.get("item_name")}
