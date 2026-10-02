# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""OSHA Form 300A - Summary of Work-Related Injuries and Illnesses (29 CFR 1904.32)."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime

from hse.hse.osha_recordkeeping import get_cases, incidence_rate, summarize


class OSHA300ASummary(Document):
	def validate(self):
		if not 2000 <= cint(self.year) <= 2100:
			frappe.throw(_("Enter a four-digit calendar year."))
		self.calculate_totals()
		self.set_dates()

	def calculate_totals(self):
		cases = get_cases(cint(self.year), include_drafts=cint(self.include_drafts))
		self.update(summarize(cases))
		recordable = self.total_deaths + self.total_days_away_cases + self.total_transfer_cases + self.total_other_cases
		self.trir = incidence_rate(recordable, self.total_hours_worked)
		self.dart_rate = incidence_rate(self.total_days_away_cases + self.total_transfer_cases, self.total_hours_worked)
		self.last_calculated = now_datetime()

	def set_dates(self):
		year = cint(self.year)
		self.post_from = f"{year + 1}-02-01"  # 1904.32(b)(6)
		self.post_until = f"{year + 1}-04-30"
		self.retain_until = f"{year + 5}-12-31"  # 1904.33(a)

	def before_submit(self):
		if self.include_drafts:
			frappe.throw(_("Turn off Count Draft Injury Reports and submit those reports before certifying."))
		if self.cases_missing_type:
			frappe.throw(
				_("{0} recordable case(s) have no OSHA Injury/Illness Classification. Fix them in the OSHA 300 Log first.").format(
					self.cases_missing_type
				)
			)
		missing = [
			self.meta.get_label(f)
			for f in ("certified_by", "certifier_title", "certification_date")
			if not self.get(f)
		]
		if missing:
			frappe.throw(_("A company executive must certify the summary. Missing: {0}").format(", ".join(missing)))
