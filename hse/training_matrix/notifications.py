# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Overdue notices, escalation and the monthly training status report (TRN-700 Rev 1 §4.9).

- The day a required course goes overdue, the employee's manager gets a ToDo.
- After Training Matrix Settings → Escalate After days (14), it escalates by email and ToDo to the
  escalation recipients (roles and / or people in Settings; HR Manager when none are set).
- On the first Monday of each month, every manager gets their team's report and the company-wide
  report goes to the report recipients (the escalation recipients when none are set).
"""

import frappe
from frappe import _
from frappe.utils import (
	add_months,
	date_diff,
	escape_html,
	get_first_day,
	get_last_day,
	get_url,
	getdate,
	today,
)

from hse.training_matrix import status as st
from hse.training_matrix.skills import manager_users

MATRIX = "Employee Training Matrix"
ITEM = "Employee Training Matrix Item"
DEFAULT_ROLE = "HR Manager"


# ---------------------------------------------------------------- recipients
def settings():
	return frappe.get_cached_doc("Training Matrix Settings")


def users_with_roles(roles) -> set[str]:
	roles = [r for r in roles if r]
	if not roles:
		return set()
	users = frappe.get_all("Has Role", filters={"role": ["in", roles], "parenttype": "User"}, pluck="parent")
	return {
		u.name
		for u in frappe.get_all(
			"User",
			filters={"name": ["in", users or [""]], "enabled": 1, "user_type": "System User"},
			fields=["name"],
		)
		if u.name not in ("Administrator", "Guest")
	}


def _recipients(roles_table, users_table) -> list[str]:
	users = users_with_roles([r.role for r in roles_table or []])
	users |= {u.user for u in users_table or [] if frappe.db.get_value("User", u.user, "enabled")}
	return sorted(users)


def escalation_recipients() -> list[str]:
	s = settings()
	return _recipients(s.escalation_roles, s.escalation_users) or sorted(users_with_roles([DEFAULT_ROLE]))


def report_recipients() -> list[str]:
	s = settings()
	return _recipients(s.report_roles, s.report_users) or escalation_recipients()


def _assign(users, doctype, name, description) -> None:
	from frappe.desk.form.assign_to import add as assign

	if not users:
		return
	try:
		assign({"assign_to": list(users), "doctype": doctype, "name": name, "description": description})
	except Exception:
		pass  # already assigned to an open ToDo


# ---------------------------------------------------------------- overdue
def overdue_rows() -> list[frappe._dict]:
	return frappe.get_all(
		ITEM,
		filters={"parenttype": MATRIX, "active": 1, "is_required": 1, "status": st.OVERDUE},
		fields=[
			"name",
			"parent",
			"employee_name",
			"department",
			"training_requirement",
			"course_title",
			"due_date",
			"overdue_since",
			"manager_notified_on",
			"escalated_on",
		],
		order_by="parent asc, training_requirement asc",
	)


def process_overdue(on_date=None) -> None:
	"""Daily, after the matrix refresh: manager ToDos for newly overdue courses, then escalation."""
	on_date = getdate(on_date or today())
	rows = overdue_rows()
	by_matrix: dict[str, list] = {}
	for r in rows:
		if not r.manager_notified_on:
			by_matrix.setdefault(r.parent, []).append(r)
	for matrix, items in by_matrix.items():
		_assign(
			manager_users(matrix),
			MATRIX,
			matrix,
			_("{0} has overdue training: {1}. Arrange it now (TRN-700 §4.9).").format(
				items[0].employee_name, ", ".join(r.training_requirement for r in items)
			),
		)
		for r in items:
			frappe.db.set_value(ITEM, r.name, "manager_notified_on", on_date, update_modified=False)

	days = settings().escalation_days or 14
	due = [
		r
		for r in rows
		if r.overdue_since and not r.escalated_on and date_diff(on_date, r.overdue_since) >= days
	]
	if not due:
		return
	recipients = escalation_recipients()
	if recipients:
		frappe.sendmail(
			recipients=recipients,
			subject=_("Training overdue {0}+ days: {1} item(s)").format(days, len(due)),
			message=_overdue_table(
				due, on_date, _("These required courses are still overdue after {0} days.").format(days)
			),
		)
		for matrix in sorted({r.parent for r in due}):
			_assign(
				recipients,
				MATRIX,
				matrix,
				_("Training overdue more than {0} days for {1}: escalated (TRN-700 §4.9).").format(
					days, next(r.employee_name for r in due if r.parent == matrix)
				),
			)
	for r in due:
		frappe.db.set_value(ITEM, r.name, "escalated_on", on_date, update_modified=False)


# ---------------------------------------------------------------- monthly report
def monthly_status_email(on_date=None) -> None:
	"""Runs every Monday; sends only on the first Monday of the month."""
	on_date = getdate(on_date or today())
	if on_date.weekday() != 0 or on_date.day > 7 or not settings().monthly_email:
		return
	send_monthly_report(on_date)


def send_monthly_report(on_date=None) -> None:
	on_date = getdate(on_date or today())
	start = get_first_day(add_months(on_date, -1))
	end = get_last_day(start)
	period = _("{0} to {1}").format(frappe.format(start, "Date"), frappe.format(end, "Date"))

	matrices = frappe.get_all(
		MATRIX,
		filters={"active": 1},
		fields=["name", "employee_name", "department", "percent_complete", "overdue_count", "due_count"],
		order_by="department asc, employee_name asc",
	)
	if not matrices:
		return
	open_rows = frappe.get_all(
		ITEM,
		filters={"parenttype": MATRIX, "active": 1, "is_required": 1, "status": ["in", [st.DUE, st.OVERDUE]]},
		fields=[
			"parent",
			"employee_name",
			"training_requirement",
			"course_title",
			"status",
			"due_date",
			"overdue_since",
		],
		order_by="status desc, due_date asc",
	)
	completed = completed_in_period([m.name for m in matrices], start, end)

	managers: dict[str, list] = {}
	for m in matrices:
		for user in manager_users_only(m.name):
			managers.setdefault(user, []).append(m)
	for user, team in managers.items():
		names = {m.name for m in team}
		frappe.sendmail(
			recipients=[user],
			subject=_("Team training status for {0}").format(period),
			message=_team_report(team, [r for r in open_rows if r.parent in names], completed, period),
		)

	recipients = report_recipients()
	if recipients:
		frappe.sendmail(
			recipients=recipients,
			subject=_("Company training status for {0}").format(period),
			message=_company_report(matrices, open_rows, completed, period, on_date),
		)


def manager_users_only(employee: str) -> list[str]:
	"""The employee's own manager's login, without the HR fallback used for ToDos."""
	manager = frappe.db.get_value("Employee", employee, "reports_to")
	user = frappe.db.get_value("Employee", manager, "user_id") if manager else None
	return [user] if user else []


def completed_in_period(employees: list[str], start, end) -> dict[str, int]:
	"""{employee: training records completed in the period}."""
	rows = frappe.get_all(
		"Training Record Attendee",
		filters={"parenttype": "Training Record", "employee": ["in", employees or [""]]},
		fields=["parent", "employee", "result"],
	)
	records = set(
		frappe.get_all(
			"Training Record",
			filters={
				"name": ["in", list({r.parent for r in rows}) or [""]],
				"docstatus": 1,
				"training_date": ["between", [start, end]],
			},
			pluck="name",
		)
	)
	out: dict[str, int] = {}
	for r in rows:
		if r.parent in records and r.result != "Fail":
			out[r.employee] = out.get(r.employee, 0) + 1
	return out


# ---------------------------------------------------------------- HTML
TABLE = 'style="border-collapse:collapse;width:100%;font-size:13px"'
TH = 'style="text-align:left;border-bottom:2px solid #ccc;padding:4px 6px"'
TD = 'style="border-bottom:1px solid #eee;padding:4px 6px"'


def _table(headers, rows) -> str:
	head = "".join(f"<th {TH}>{escape_html(h)}</th>" for h in headers)
	body = "".join("<tr>" + "".join(f"<td {TD}>{c}</td>" for c in row) + "</tr>" for row in rows)
	return f"<table {TABLE}><tr>{head}</tr>{body}</table>"


def _link(matrix: str, label: str) -> str:
	return (
		f'<a href="{get_url("/app/employee-training-matrix/" + matrix)}">{escape_html(label or matrix)}</a>'
	)


def _overdue_table(rows, on_date, intro) -> str:
	return f"<p>{escape_html(intro)}</p>" + _table(
		[_("Employee"), _("Course"), _("Due"), _("Days overdue")],
		[
			[
				_link(r.parent, r.employee_name),
				escape_html(f"{r.training_requirement} {r.course_title or ''}"),
				frappe.format(r.due_date, "Date"),
				str(date_diff(on_date, r.overdue_since)) if r.overdue_since else "",
			]
			for r in rows
		],
	)


def _open_table(rows) -> str:
	if not rows:
		return f"<p>{_('Nothing due or overdue.')}</p>"
	return _table(
		[_("Employee"), _("Course"), _("Status"), _("Due")],
		[
			[
				_link(r.parent, r.employee_name),
				escape_html(f"{r.training_requirement} {r.course_title or ''}"),
				f"<b>{_(r.status)}</b>" if r.status == st.OVERDUE else _(r.status),
				frappe.format(r.due_date, "Date"),
			]
			for r in rows
		],
	)


def _team_report(team, open_rows, completed, period) -> str:
	summary = _table(
		[_("Employee"), _("% Complete"), _("Completed in period"), _("Due in 30 days"), _("Overdue")],
		[
			[
				_link(m.name, m.employee_name),
				f"{m.percent_complete or 0:.0f}%",
				str(completed.get(m.name, 0)),
				str(m.due_count or 0),
				f"<b>{m.overdue_count}</b>" if m.overdue_count else "0",
			]
			for m in team
		],
	)
	return (
		f"<p>{escape_html(_('Training status for your team, {0} (TRN-700 §4.9).').format(period))}</p>"
		+ summary
		+ f"<h4>{_('Due and overdue')}</h4>"
		+ _open_table(open_rows)
	)


def _company_report(matrices, open_rows, completed, period, on_date) -> str:
	departments: dict[str, dict] = {}
	for m in matrices:
		d = departments.setdefault(
			m.department or _("No Department"), {"n": 0, "pct": 0.0, "due": 0, "overdue": 0, "done": 0}
		)
		d["n"] += 1
		d["pct"] += m.percent_complete or 0
		d["due"] += m.due_count or 0
		d["overdue"] += m.overdue_count or 0
		d["done"] += completed.get(m.name, 0)
	summary = _table(
		[
			_("Department"),
			_("Employees"),
			_("Average % Complete"),
			_("Completed in period"),
			_("Due in 30 days"),
			_("Overdue"),
		],
		[
			[
				escape_html(dept),
				str(d["n"]),
				f"{d['pct'] / d['n']:.0f}%",
				str(d["done"]),
				str(d["due"]),
				f"<b>{d['overdue']}</b>" if d["overdue"] else "0",
			]
			for dept, d in sorted(departments.items())
		],
	)
	days = settings().escalation_days or 14
	long_overdue = [
		r
		for r in open_rows
		if r.status == st.OVERDUE and r.overdue_since and date_diff(on_date, r.overdue_since) >= days
	]
	return (
		f"<p>{escape_html(_('Company-wide training status, {0} (TRN-700 §4.9).').format(period))}</p>"
		+ summary
		+ f"<h4>{escape_html(_('Overdue {0}+ days').format(days))}</h4>"
		+ (_overdue_table(long_overdue, on_date, "") if long_overdue else f"<p>{_('None.')}</p>")
	)
