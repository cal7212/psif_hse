# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Corrective actions move from single fields on the Injury_Illness Report to the Corrective
Actions table. Each report's existing action becomes row 1. The old columns stay in the
database (Frappe does not drop them) and are read directly here. Next Action Due and All
Actions Completed are then recalculated from the table."""

import frappe
from frappe.utils import cstr

from hse.hse.doctype.injury_illness_report.injury_illness_report import corrective_action_summary

PARENT = "Injury_Illness Report"
CHILD = "Incident Corrective Action"
OLD_FIELDS = (
	"title",
	"action_type",
	"ca_location",
	"priority",
	"assigned_to",
	"responsible_party",
	"date_due",
	"date_start",
	"date_done",
	"date_verify",
	"task_description",
	"attachments",
	"task_notes",
)


def execute():
	fields = [f for f in OLD_FIELDS if frappe.db.has_column(PARENT, f)]
	if not fields:
		return
	have_rows = set(frappe.get_all(CHILD, filters={"parenttype": PARENT}, pluck="parent", distinct=True))
	cols = ", ".join(f"`{f}`" for f in fields)
	moved = 0
	for old in frappe.db.sql(f"select name, {cols} from `tab{PARENT}`", as_dict=True):
		if old.name in have_rows or not any(cstr(old.get(f)).strip() for f in fields):
			continue
		row = frappe.get_doc(
			{
				"doctype": CHILD,
				"parent": old.name,
				"parenttype": PARENT,
				"parentfield": "corrective_actions",
				"idx": 1,
				**{f: old.get(f) for f in fields},
			}
		)
		if not cstr(row.title).strip():
			# Action is required on new rows; describe untitled ones from what they hold.
			row.title = (cstr(row.task_description).strip().splitlines() or ["Corrective action"])[0][:140]
		row.db_insert()
		due, done = corrective_action_summary([row])
		frappe.db.set_value(PARENT, old.name, {"date_due": due, "date_done": done}, update_modified=False)
		moved += 1
	if moved:
		print(f"Moved the corrective action of {moved} injury/illness report(s) into the Corrective Actions table.")
