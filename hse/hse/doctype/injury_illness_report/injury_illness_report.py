# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, date_diff, getdate

DAY_CAP = 180  # 29 CFR 1904.7(b)(3)(vii): total may be capped at 180 calendar days
DAY_TABLES = ("days_away", "job_restriction")


def count_days(start_date, return_date, incident_date=None):
	"""Calendar days from start_date up to (not including) return_date.

	Per 29 CFR 1904.7(b)(3)(i) counting begins the day after the injury, so a
	start date on (or before) the incident date is moved to the next day.
	Weekends and days off are included (1904.7(b)(3)(iv))."""
	if not start_date or not return_date:
		return 0
	start = getdate(start_date)
	if incident_date:
		start = max(start, getdate(add_days(incident_date, 1)))
	return max(date_diff(return_date, start), 0)


def apply_cap(day_counts, cap=DAY_CAP):
	"""Cap the running total of a table at `cap`; later rows get what is left."""
	remaining, out = cap, []
	for days in day_counts:
		used = min(days, remaining)
		out.append(used)
		remaining -= used
	return out


class Injury_IllnessReport(Document):
	def validate(self):
		self.calculate_days()

	def calculate_days(self):
		for table in DAY_TABLES:
			rows = self.get(table) or []
			for row in rows:
				if row.start_date and row.return_date and getdate(row.return_date) < getdate(row.start_date):
					frappe.throw(
						_("{0} row {1}: Return Date cannot be before Start Date.").format(
							self.meta.get_label(table), row.idx
						)
					)
			raw = [count_days(r.start_date, r.return_date, self.incident_date) for r in rows]
			capped = apply_cap(raw)
			for row, days in zip(rows, capped, strict=True):
				row.number_of_days_away = days
			if sum(raw) > DAY_CAP:
				frappe.msgprint(
					_("{0} total exceeds {1} days and has been capped at {1}.").format(
						self.meta.get_label(table), DAY_CAP
					),
					indicator="orange",
					alert=True,
				)
