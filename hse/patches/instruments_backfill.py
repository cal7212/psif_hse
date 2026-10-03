# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Move the old fixed gauge / flowmeter fields on QC Inspection into the Test Equipment
table (creating Measuring Instrument records as needed), and add a Test Equipment card
to the Systems workspace. Safe to re-run."""

import json

import frappe

WORKSPACE = "Systems"
CARD = "Test Equipment"
OLD = (("gauge_id", "gauge_cal_due", "Pressure Gauge"), ("flowmeter_id", "flowmeter_cal_due", "Flowmeter"))


def execute():
	backfill_inspections()
	add_workspace_card()


def backfill_inspections():
	columns = set(frappe.db.get_table_columns("QC Inspection"))
	for id_col, due_col, itype in OLD:
		if id_col not in columns:
			continue
		qi = frappe.qb.DocType("QC Inspection")
		rows = (
			frappe.qb.from_(qi)
			.select(qi.name, qi[id_col].as_("instrument"), qi[due_col].as_("due"))
			.where(qi[id_col].isnotnull() & (qi[id_col] != ""))
			.run(as_dict=True)
		)
		for r in rows:
			iid = r.instrument.strip().upper()
			if not frappe.db.exists("Measuring Instrument", iid):
				frappe.get_doc(
					{
						"doctype": "Measuring Instrument",
						"instrument_id": iid,
						"instrument_type": itype,
						"calibration_due": r.due,
						"description": f"Created from {r.name}",
					}
				).insert(ignore_permissions=True)
			if frappe.db.exists(
				"Inspection Instrument", {"parenttype": "QC Inspection", "parent": r.name, "instrument": iid}
			):
				continue
			idx = frappe.db.count("Inspection Instrument", {"parenttype": "QC Inspection", "parent": r.name})
			frappe.get_doc(
				{
					"doctype": "Inspection Instrument",
					"parenttype": "QC Inspection",
					"parentfield": "instruments",
					"parent": r.name,
					"idx": idx + 1,
					"instrument": iid,
					"instrument_type": itype,
					"calibration_due": r.due,
				}
			).db_insert()


def add_workspace_card():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return
	ws = frappe.get_doc("Workspace", WORKSPACE)
	if any(link.type == "Card Break" and link.label == CARD for link in ws.links):
		return
	ws.append("links", {"type": "Card Break", "label": CARD, "link_type": "DocType", "link_count": 2})
	ws.append(
		"links",
		{
			"type": "Link",
			"label": "Measuring Instruments",
			"link_type": "DocType",
			"link_to": "Measuring Instrument",
		},
	)
	ws.append(
		"links",
		{
			"type": "Link",
			"label": "Instrument Usage",
			"link_type": "Report",
			"link_to": "Instrument Usage",
			"is_query_report": 1,
			"dependencies": "",
		},
	)
	content = json.loads(ws.content or "[]")
	if not any(b.get("type") == "card" and b.get("data", {}).get("card_name") == CARD for b in content):
		content.append(
			{"id": frappe.generate_hash(length=10), "type": "card", "data": {"card_name": CARD, "col": 4}}
		)
		ws.content = json.dumps(content)
	ws.save(ignore_permissions=True)
