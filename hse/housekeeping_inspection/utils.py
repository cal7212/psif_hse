import frappe
from frappe import _
from frappe.utils import add_days, add_months, getdate, today

SATISFACTORY = "Satisfactory"
ACTION_REQUIRED = "Action Required"
HAZARD_OPEN = "Hazard Open"

PERIOD_DAYS = {"Daily": 1, "Weekly": 7}
PERIOD_MONTHS = {"Monthly": 1, "Quarterly": 3}
AS_NEEDED = "As Needed"
NOT_SCHEDULED = "Not Scheduled"
AWAITING_RETURN = "Awaiting Return"


def next_due(from_date, periodicity: str):
	"""Next due date one period after from_date (None for As Needed areas)."""
	if periodicity == AS_NEEDED:
		return None
	from_date = getdate(from_date)
	if periodicity in PERIOD_DAYS:
		return add_days(from_date, PERIOD_DAYS[periodicity])
	if periodicity in PERIOD_MONTHS:
		return add_months(from_date, PERIOD_MONTHS[periodicity])
	frappe.throw(_("Unsupported periodicity: {0}").format(periodicity))


def schedule_status_for(next_due_date, on_date=None, periodicity=None) -> str:
	if periodicity == AS_NEEDED:
		return NOT_SCHEDULED
	if not next_due_date:
		return "Current"
	on_date = getdate(on_date or today())
	due = getdate(next_due_date)
	if due < on_date:
		return "Overdue"
	if due == on_date:
		return "Due"
	return "Current"


def update_area_housekeeping_status(area: str) -> str | None:
	"""Hazard Open while any Open Critical Non Conformance exists for the area,
	Action Required while any other Open one exists, otherwise Satisfactory."""
	if not area or not frappe.db.exists("Housekeeping Area", area):
		return None

	open_ncs = frappe.get_all(
		"Non Conformance",
		filters={"housekeeping_area": area, "status": "Open"},
		pluck="severity",
	)
	if "Critical" in open_ncs:
		new_status = HAZARD_OPEN
	elif open_ncs:
		new_status = ACTION_REQUIRED
	else:
		new_status = SATISFACTORY

	if frappe.db.get_value("Housekeeping Area", area, "housekeeping_status") != new_status:
		frappe.db.set_value("Housekeeping Area", area, "housekeeping_status", new_status)
		frappe.get_doc("Housekeeping Area", area).add_comment(
			"Info", "Housekeeping Status set to " + new_status
		)
	return new_status


def trip_status(reason: str | None, current: str | None = None) -> str:
	"""Schedule status of an As Needed area after an inspection with this reason."""
	if reason == "Pre-Departure":
		return AWAITING_RETURN
	if reason == "Post-Return":
		return NOT_SCHEDULED
	return current if current == AWAITING_RETURN else NOT_SCHEDULED


def refresh_area_last_inspection(area: str):
	"""Point the area at its most recent submitted routine (non re-) inspection.
	Used after cancel so the area does not keep a cancelled inspection."""
	last = frappe.get_all(
		"Housekeeping Inspection",
		filters={"housekeeping_area": area, "docstatus": 1, "is_reinspection": 0},
		fields=["name", "inspection_date", "score", "inspection_reason"],
		order_by="inspection_date desc",
		limit=1,
	)
	if last:
		values = {
			"last_inspection": last[0].name,
			"last_inspection_date": getdate(last[0].inspection_date),
			"last_score": last[0].score,
		}
	else:
		values = {"last_inspection": None, "last_inspection_date": None, "last_score": 0}
	if frappe.db.get_value("Housekeeping Area", area, "periodicity") == AS_NEEDED:
		values["schedule_status"] = trip_status(last[0].inspection_reason if last else None)
	frappe.db.set_value("Housekeeping Area", area, values)


def close_area_todos(area: str):
	"""Close open scheduler ToDos for this area once it has been inspected."""
	for name in frappe.get_all(
		"ToDo",
		filters={"reference_type": "Housekeeping Area", "reference_name": area, "status": "Open"},
		pluck="name",
	):
		frappe.db.set_value("ToDo", name, "status", "Closed")
