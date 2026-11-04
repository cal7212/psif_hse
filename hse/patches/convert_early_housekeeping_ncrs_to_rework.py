"""Housekeeping failures raised as NCRs before the Rework rule (Oct 5-6, 2026) become Rework.

Record Type is set-only-once, so it is changed directly. Only Open, draft records from a
Housekeeping Inspection with no CAPA or SCAR are touched; names stay as they are.
Runs once."""

import frappe

NAMES = ["QA-NC-00360", "QA-NC-00368", "QA-NC-00369", "QA-NC-00370"]


def execute():
	dt = "Nonconformance Report"
	if not frappe.db.has_column(dt, "record_type"):
		return
	for name in NAMES:
		row = frappe.db.get_value(
			dt,
			{
				"name": name,
				"record_type": "NCR",
				"source": "Housekeeping Inspection",
				"status": "Open",
				"docstatus": 0,
				"capa_required": 0,
				"scar_required": 0,
			},
			["name", "details", "rw_requirement"],
			as_dict=True,
		)
		if not row:
			continue
		values = {"record_type": "Rework"}
		if not row.rw_requirement and row.details:
			values["rw_requirement"] = row.details
		frappe.db.set_value(dt, name, values, update_modified=False)
		frappe.get_doc(dt, name).add_comment(
			"Info",
			"Converted from NCR to Rework: housekeeping failures are Rework unless they meet the "
			"QM-104 NCR criteria. Complete the NCR Criteria Evaluation; use Escalate to NCR if met.",
		)
