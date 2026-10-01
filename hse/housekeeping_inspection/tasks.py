import frappe
from frappe import _
from frappe.utils import getdate, today

from hse.housekeeping_inspection.utils import schedule_status_for


def update_schedules():
	"""Daily: refresh Due/Overdue status on every area and give the assigned
	inspector a ToDo when an inspection comes due (one open ToDo per area).
	As Needed areas (e.g. job trailers) have no due date and are skipped."""
	areas = frappe.get_all(
		"Housekeeping Area",
		filters={"disabled": 0, "periodicity": ["!=", "As Needed"]},
		fields=["name", "next_due_date", "schedule_status", "inspector_user", "periodicity"],
	)
	for area in areas:
		status = schedule_status_for(area.next_due_date)
		if status != area.schedule_status:
			frappe.db.set_value(
				"Housekeeping Area", area.name, "schedule_status", status, update_modified=False
			)

		if status == "Current" or not area.inspector_user:
			continue
		if frappe.db.exists(
			"ToDo",
			{"reference_type": "Housekeeping Area", "reference_name": area.name, "status": "Open"},
		):
			continue
		frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": area.inspector_user,
				"reference_type": "Housekeeping Area",
				"reference_name": area.name,
				"date": getdate(area.next_due_date) if area.next_due_date else today(),
				"priority": "High" if status == "Overdue" else "Medium",
				"description": _("{0} housekeeping inspection due for {1}").format(
					area.periodicity, area.name
				),
			}
		).insert(ignore_permissions=True)
	# No manual commit: Frappe commits when a scheduled job finishes.
