# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Every QC inspection and asset inspection an instrument was used on. Run it when an
instrument fails calibration to find the work that needs review."""

import frappe
from frappe import _
from frappe.query_builder.functions import Count
from frappe.utils import add_days

SOURCES = {
	# inspection doctype: (reading tables with instrument fields, subject field, step field)
	"QC Inspection": (
		[
			("QC Inspection Reading", "instrument"),
			("QC Hose Test", "instrument"),
			("QC Hose Test", "crimp_instrument"),
			("QC Hose Test", "particle_counter"),
			("QC PMG Test", "instrument"),
			("QC PMG Test", "amps_instrument"),
			("QC Accumulator Test", "instrument"),
			("QC Proof Test", "instrument"),
		],
		"qc_unit",
		"stage",
	),
	"Asset Inspection": ([("Asset Inspection Reading", "instrument")], "asset", "template"),
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.instrument:
		return get_columns(), []
	data = []
	for doctype in SOURCES:
		if not filters.inspection_type or filters.inspection_type == doctype:
			data += get_rows(doctype, filters)
	data.sort(key=lambda r: r.inspection_date)
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Type"), "fieldname": "inspection_type", "fieldtype": "Data", "width": 120},
		{
			"label": _("Inspection"),
			"fieldname": "inspection",
			"fieldtype": "Dynamic Link",
			"options": "inspection_type",
			"width": 160,
		},
		{"label": _("Date"), "fieldname": "inspection_date", "fieldtype": "Datetime", "width": 150},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{"label": _("Unit / Asset"), "fieldname": "subject", "fieldtype": "Data", "width": 140},
		{"label": _("Stage / Template"), "fieldname": "step", "fieldtype": "Data", "width": 200},
		{"label": _("Readings"), "fieldname": "readings", "fieldtype": "Int", "width": 80},
		{"label": _("Cal Due (at use)"), "fieldname": "calibration_due", "fieldtype": "Date", "width": 120},
	]


def get_rows(doctype, filters):
	tables, subject, step = SOURCES[doctype]
	parent = frappe.qb.DocType(doctype)
	ins = frappe.qb.DocType("Inspection Instrument")
	q = (
		frappe.qb.from_(ins)
		.join(parent)
		.on(parent.name == ins.parent)
		.select(
			parent.name.as_("inspection"),
			parent.inspection_date,
			parent.status,
			parent[subject].as_("subject"),
			parent[step].as_("step"),
			ins.calibration_due,
		)
		.where((ins.parenttype == doctype) & (ins.instrument == filters.instrument) & (parent.docstatus < 2))
	)
	if filters.from_date:
		q = q.where(parent.inspection_date >= filters.from_date)
	if filters.to_date:
		q = q.where(parent.inspection_date < add_days(filters.to_date, 1))
	rows = q.run(as_dict=True)
	if not rows:
		return []

	names = [r.inspection for r in rows]
	counts = {}
	for table, field in tables:
		t = frappe.qb.DocType(table)
		for name, n in (
			frappe.qb.from_(t)
			.select(t.parent, Count("*"))
			.where((t[field] == filters.instrument) & t.parent.isin(names))
			.groupby(t.parent)
			.run()
		):
			counts[name] = counts.get(name, 0) + n
	for r in rows:
		r.inspection_type = doctype
		r.readings = counts.get(r.inspection, 0)
	return rows
