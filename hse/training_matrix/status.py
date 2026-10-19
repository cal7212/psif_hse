# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Status rules for TRN-701 Employee Training Matrix rows (TRN-700 Rev 1).

Kept free of database calls so the daily refresh, the form, the reports and the
quality metrics all use one definition of Due, Overdue and Qualified.

A row is Qualified when the training has been completed and is still current:
the refresher (or certificate) is not past its due date. A lapsed refresher or an
expired certificate makes the row Overdue and Not Qualified until it is redone.
"""

from datetime import date

from frappe.utils import add_days, add_months, formatdate, getdate

# Part 1 requirement codes
REQUIRED, CONDITIONAL, NOT_REQUIRED = "R", "C", "—"
# Development: needed for a target skill the manager set; tracked but outside compliance.
DEVELOPMENT = "Dev"
APPLIES, DOES_NOT_APPLY = "Applies", "Not Applicable"

# Row statuses (Part 2 codes in brackets)
NOT_STARTED = "Not Started"
IN_PROGRESS = "In Progress"  # IP
DUE = "Due"  # D: due within 30 days
OVERDUE = "Overdue"  # OD
COMPLETED = "Completed"  # C / date
CONFIRM = "Confirm Applicability"  # conditional item the manager has not confirmed
NOT_APPLICABLE = "Not Applicable"  # —
STATUSES = (NOT_STARTED, IN_PROGRESS, DUE, OVERDUE, COMPLETED, CONFIRM, NOT_APPLICABLE)

QUALIFIED, NOT_QUALIFIED = "Qualified", "Not Qualified"

DUE_WINDOW_DAYS = 30  # TRN-700 §4.9: due within 30 days is communicated

# Initial due date basis
HIRE, ASSIGNED = "Date of Hire", "Date Assigned"

# Refresher frequencies
ONE_TIME = "One-time"
PER_CERTIFICATION = "Per Certification"
REFRESHER_MONTHS = {
	ONE_TIME: None,
	"Annually": 12,
	"Every 2 Years": 24,
	"Every 3 Years": 36,
	PER_CERTIFICATION: None,
}
FREQUENCIES = tuple(REFRESHER_MONTHS)


def _d(value) -> date | None:
	return getdate(value) if value else None


def is_required(code: str | None, applicability: str | None) -> bool:
	return code == REQUIRED or (code == CONDITIONAL and applicability == APPLIES)


def initial_due_date(basis: str | None, days, hire_date, assigned_on) -> date | None:
	start = _d(hire_date) if basis == HIRE else _d(assigned_on)
	if basis == HIRE and start is None:
		start = _d(assigned_on)
	if start is None:
		return None
	return getdate(add_days(start, int(days or 0)))


def next_due_date(frequency: str | None, completed_on, expires_on) -> date | None:
	"""When completed training next falls due: refresher interval or certificate expiry."""
	if frequency == PER_CERTIFICATION:
		return _d(expires_on)
	months = REFRESHER_MONTHS.get(frequency)
	if months and completed_on:
		return getdate(add_months(_d(completed_on), months))
	# one-time training can still carry an expiry (e.g. an external certificate)
	return _d(expires_on)


def evaluate(row: dict, requirement: dict, hire_date, today, assigned_override=None) -> dict:
	"""Status of one matrix row.

	row: requirement_code, applicability, assigned_on, in_progress, completed_on, expires_on,
	     development_due (Dev rows: the manager's target date)
	requirement: initial_due_basis, initial_due_days, refresher_frequency
	Returns status, qualification, due_date, is_required.
	"""
	today = getdate(today)
	code, applicability = row.get("requirement_code"), row.get("applicability")

	if code == DEVELOPMENT:
		override = None if row.get("completed_on") else row.get("development_due")
		if override:  # due on the manager's target date
			requirement = {**requirement, "initial_due_basis": ASSIGNED, "initial_due_days": 0}
		result = evaluate({**row, "requirement_code": REQUIRED}, requirement, hire_date, today, override)
		return {**result, "is_required": 0}

	if code == CONDITIONAL and not applicability:
		return _result(CONFIRM, NOT_QUALIFIED, None, False)
	if not is_required(code, applicability):
		return _result(NOT_APPLICABLE, _held(row, requirement, today), None, False)

	completed_on = _d(row.get("completed_on"))
	if completed_on:
		due = next_due_date(requirement.get("refresher_frequency"), completed_on, row.get("expires_on"))
		if due is None:
			return _result(COMPLETED, QUALIFIED, None, True)
		if today > due:
			return _result(OVERDUE, NOT_QUALIFIED, due, True)
		if (due - today).days <= DUE_WINDOW_DAYS:
			return _result(DUE, QUALIFIED, due, True)
		return _result(COMPLETED, QUALIFIED, due, True)

	due = initial_due_date(
		requirement.get("initial_due_basis"),
		requirement.get("initial_due_days"),
		hire_date,
		assigned_override or row.get("assigned_on"),
	)
	if due and today > due:
		return _result(OVERDUE, NOT_QUALIFIED, due, True)
	if row.get("in_progress"):
		return _result(IN_PROGRESS, NOT_QUALIFIED, due, True)
	if due and (due - today).days <= DUE_WINDOW_DAYS:
		return _result(DUE, NOT_QUALIFIED, due, True)
	return _result(NOT_STARTED, NOT_QUALIFIED, due, True)


def _held(row: dict, requirement: dict, today) -> str:
	"""Qualification on a row that is no longer required (history kept for the record)."""
	if not row.get("completed_on"):
		return NOT_QUALIFIED
	due = next_due_date(
		requirement.get("refresher_frequency"), row.get("completed_on"), row.get("expires_on")
	)
	return NOT_QUALIFIED if due and today > due else QUALIFIED


def _result(status, qualification, due_date, required) -> dict:
	return {
		"status": status,
		"qualification": qualification,
		"due_date": due_date,
		"is_required": 1 if required else 0,
	}


def percent_complete(rows: list[dict]) -> float:
	"""Appendix A Part 2: completed required courses ÷ total required courses."""
	required = [r for r in rows if r.get("is_required")]
	if not required:
		return 0.0
	done = sum(1 for r in required if r.get("qualification") == QUALIFIED)
	return round(done / len(required) * 100, 1)


def matrix_code(status: str | None, completed_on=None) -> str:
	"""Cell text for the Part 2 grid."""
	if status in (COMPLETED,) and completed_on:
		return "C " + formatdate(completed_on, "mm/dd/yy")
	return {
		IN_PROGRESS: "IP",
		DUE: "D",
		OVERDUE: "OD",
		CONFIRM: "?",
		NOT_APPLICABLE: NOT_REQUIRED,
		NOT_STARTED: "",
	}.get(status or "", "")


def frequency_summary(
	basis: str | None, days, frequency: str | None, retrain_on_revision=0, notes: str | None = None
) -> str:
	"""Readable Frequency column for Part 1, e.g. 'Upon hire; annually; new chemical hazard'."""
	days = int(days or 0)
	if basis == HIRE:
		parts = ["Upon hire" if days == 0 else f"Within {days} days of hire"]
	else:
		parts = ["Upon assignment" if days == 0 else f"Within {days} days of assignment"]
	freq = {
		"Annually": "annually",
		"Every 2 Years": "every 2 years",
		"Every 3 Years": "every 3 years",
		PER_CERTIFICATION: "per certification",
	}.get(frequency or "")
	if freq:
		parts.append(freq)
	if retrain_on_revision:
		parts.append("on revision")
	if notes:
		parts.append(notes)
	return "; ".join(parts)
