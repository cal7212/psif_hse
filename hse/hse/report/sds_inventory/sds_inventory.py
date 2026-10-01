# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Hazardous chemical inventory by location (29 CFR 1910.1200(e)(1)(i)).
Product names match the SDS and label, with a link to each SDS."""

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Location"), "fieldname": "location", "fieldtype": "Link", "options": "Location", "width": 150},
		{"label": _("Storage Detail"), "fieldname": "storage_detail", "fieldtype": "Data", "width": 160},
		{"label": _("Product"), "fieldname": "product_name", "fieldtype": "Data", "width": 200},
		{"label": _("SDS"), "fieldname": "sds", "fieldtype": "Link", "options": "SDS", "width": 120},
		{"label": _("Manufacturer"), "fieldname": "manufacturer_name", "fieldtype": "Data", "width": 170},
		{"label": _("Signal Word"), "fieldname": "signal_word", "fieldtype": "Data", "width": 100},
		{"label": _("Pictograms"), "fieldname": "pictograms", "fieldtype": "Data", "width": 180},
		{"label": _("Containers"), "fieldname": "quantity", "fieldtype": "Float", "width": 90},
		{"label": _("Size"), "fieldname": "size", "fieldtype": "Data", "width": 90},
		{"label": _("In Use Since"), "fieldname": "start_date", "fieldtype": "Date", "width": 100},
		{"label": _("Removed"), "fieldname": "end_date", "fieldtype": "Date", "width": 100},
		{"label": _("SDS Revision"), "fieldname": "version_date", "fieldtype": "Date", "width": 100},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Needs SDS"), "fieldname": "needs_sds", "fieldtype": "Check", "width": 80},
		{"label": _("SDS File"), "fieldname": "attach_sds", "fieldtype": "Data", "width": 90},
	]


def get_data(filters):
	sds = frappe.qb.DocType("SDS")
	loc = frappe.qb.DocType("SDS Location")
	q = (
		frappe.qb.from_(sds)
		.left_join(loc)
		.on((loc.parent == sds.name) & (loc.parenttype == "SDS") & (loc.parentfield == "locations"))
		.select(
			loc.location, loc.storage_detail, sds.product_name, sds.name.as_("sds"), sds.manufacturer_name,
			sds.signal_word, loc.quantity, loc.container_size, loc.uom, loc.start_date, loc.end_date,
			sds.version_date, sds.status, sds.sds_uploaded, sds.attach_sds,
		)
		.orderby(loc.location)
		.orderby(sds.product_name)
	)
	if filters.status:
		q = q.where(sds.status == filters.status)
	if filters.location:
		lft, rgt = frappe.db.get_value("Location", filters.location, ["lft", "rgt"])
		children = frappe.get_all("Location", filters={"lft": [">=", lft], "rgt": ["<=", rgt]}, pluck="name")
		q = q.where(loc.location.isin(children))
	if filters.current_only:
		q = q.where(loc.end_date.isnull())
	if filters.unassigned_only:
		q = q.where(loc.location.isnull())

	rows = q.run(as_dict=True)
	pictos = {}
	names = list({r.sds for r in rows})
	if names:
		for p in frappe.get_all("SDS Pictogram", filters={"parenttype": "SDS", "parent": ["in", names]}, fields=["parent", "pictogram"]):
			pictos.setdefault(p.parent, []).append(p.pictogram)

	for r in rows:
		r.pictograms = ", ".join(pictos.get(r.sds, []))
		r.size = " ".join(str(x) for x in (r.pop("container_size") or "", r.pop("uom") or "") if x)
		r.needs_sds = 1 if (r.pop("sds_uploaded") or not r.attach_sds) else 0
		r.attach_sds = f'<a href="{r.attach_sds}" target="_blank">{_("Open")}</a>' if r.attach_sds else ""
		r.location = r.location or _("Not assigned")
	return rows
