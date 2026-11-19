# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cstr, date_diff, getdate, today

DAY_CAP = 180  # 29 CFR 1904.7(b)(3)(vii): total may be capped at 180 calendar days
DAY_TABLES = ("days_away", "job_restriction")
WHY_FIELDS = ("why_1", "why_2", "why_3", "why_4", "why_5")


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


def five_whys_errors(doc) -> list[str]:
	"""Each why answers the one before it, so they are filled in order, starting from a
	problem statement. Blank is fine: not every report needs a 5 Whys."""
	answered = [bool(cstr(doc.get(f)).strip()) for f in WHY_FIELDS]
	errors = []
	if any(answered) and not cstr(doc.get("five_whys_problem")).strip():
		errors.append(_("5 Whys: enter the Problem Statement the whys start from."))
	last = max((n for n, a in enumerate(answered, 1) if a), default=0)
	for n in range(1, last):
		if not answered[n - 1]:
			errors.append(_("5 Whys: answer Why {0} before Why {1}.").format(n, n + 1))
	return errors


def corrective_action_summary(rows) -> tuple:
	"""(Next Action Due, All Actions Completed) for the report, from its corrective actions.
	While any action is open: the earliest due date among the open ones, and no completion
	date. Once every action is completed: no due date, and the latest completion date. The
	dashboards count a report as overdue on these two fields."""
	if not rows:
		return None, None
	open_rows = [r for r in rows if not r.date_done]
	if open_rows:
		due = [getdate(r.date_due) for r in open_rows if r.date_due]
		return (min(due) if due else None), None
	return None, max(getdate(r.date_done) for r in rows)


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
		self.set_status_label()
		self.calculate_days()
		self.validate_five_whys()
		self.validate_sign_off()
		self.set_corrective_action_summary()

	def before_update_after_submit(self):
		# Corrective actions are usually finished after the report is submitted.
		self.set_corrective_action_summary()

	def set_corrective_action_summary(self):
		self.date_due, self.date_done = corrective_action_summary(self.corrective_actions)

	def validate_sign_off(self):
		"""A signature belongs to the person named as completing the report."""
		if self.completed_by_signature and not self.completed_by:
			frappe.throw(_("Select who completed the report (Completed By) before signing it."), title=_("Sign-off"))
		if self.completed_by_signature and not self.completed_by_date:
			self.completed_by_date = today()

	def validate_five_whys(self):
		if errors := five_whys_errors(self):
			frappe.throw("<br>".join(errors), title=_("5 Whys"))

	def set_status_label(self):
		"""Mirror Is Recordable into status_label (options: checked / unchecked)."""
		self.status_label = "checked" if self.is_recordable else "unchecked"

	def calculate_days(self):
		for table in DAY_TABLES:
			rows = self.get(table) or []
			for row in rows:
				if row.start_date and row.return_date and getdate(row.return_date) < getdate(row.start_date):
					frappe.throw(
						_("{0} row {1}: Return Date cannot be before Start Date.").format(
							_(self.meta.get_label(table)), row.idx
						)
					)
			raw = [count_days(r.start_date, r.return_date, self.incident_date) for r in rows]
			capped = apply_cap(raw)
			for row, days in zip(rows, capped, strict=True):
				row.number_of_days_away = days
			if sum(raw) > DAY_CAP:
				frappe.msgprint(
					_("{0} total exceeds {1} days and has been capped at {1}.").format(
						_(self.meta.get_label(table)), DAY_CAP
					),
					indicator="orange",
					alert=True,
				)
