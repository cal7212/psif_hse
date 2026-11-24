# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Every change order across QC Units with its review, authorisation and action status: the
retained documented information for ISO 9001 8.3.6 (design changes) and 8.5.6 (production changes)."""

import frappe
from frappe import _
from frappe.utils import cstr

from hse.shop_qc.change_control import APPROVED, IMPACT_FIELDS, PENDING


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	def col(label, fieldname, fieldtype="Data", width=110, options=None):
		c = {"label": _(label), "fieldname": fieldname, "fieldtype": fieldtype, "width": width}
		if options:
			c["options"] = options
		return c

	return [
		col("QC Unit", "qc_unit", "Link", 130, "QC Unit"),
		col("Customer", "customer_name", width=150),
		col("CO No.", "co_no", width=100),
		col("Date", "co_date", "Date", 95),
		col("Type", "change_type", width=95),
		col("Source", "source", width=130),
		col("Change", "description", width=240),
		col("From Rev", "from_rev", width=70),
		col("To Rev", "to_rev", width=70),
		col("Impacts", "impacts", width=200),
		col("Review Results", "review_results", width=240),
		col("Reviewed By", "reviewed_by", "Link", 140, "User"),
		col("Status", "status", width=90),
		col("Approved By", "approved_by", "Link", 140, "User"),
		col("Approved On", "approved_on", "Datetime", 150),
		col("Approval Reference", "approval_reference", width=160),
		col("Re-inspected Stages", "affected_stages", width=160),
		col("Actions Required", "actions_required", width=240),
		col("Actions Complete", "actions_complete", "Check", 80),
		col("Actions Verified By", "actions_verified_by", "Link", 140, "User"),
		col("Open", "open_reason", width=150),
	]


def get_data(filters):
	conds = {"parenttype": "QC Unit"}
	if filters.qc_unit:
		conds["parent"] = filters.qc_unit
	for f in ("change_type", "status", "source"):
		if filters.get(f):
			conds[f] = filters.get(f)
	if filters.from_date and filters.to_date:
		conds["co_date"] = ("between", (filters.from_date, filters.to_date))
	elif filters.from_date:
		conds["co_date"] = (">=", filters.from_date)
	elif filters.to_date:
		conds["co_date"] = ("<=", filters.to_date)

	rows = frappe.get_all(
		"QC Change Order",
		filters=conds,
		fields=[
			"parent as qc_unit",
			"co_no",
			"co_date",
			"change_type",
			"source",
			"description",
			"from_rev",
			"to_rev",
			"review_results",
			"reviewed_by",
			"status",
			"approved_by",
			"approved_on",
			"approval_reference",
			"affected_stages",
			"actions_required",
			"actions_complete",
			"actions_verified_by",
			*IMPACT_FIELDS,
		],
		order_by="co_date desc, parent asc, idx asc",
	)
	units = {r.qc_unit for r in rows}
	customers = {}
	if units:
		customers = dict(
			frappe.get_all(
				"QC Unit", filters={"name": ("in", units)}, fields=["name", "customer_name"], as_list=True
			)
		)
	meta = frappe.get_meta("QC Change Order")

	data = []
	for r in rows:
		r.customer_name = customers.get(r.qc_unit)
		r.impacts = ", ".join(_(meta.get_label(f)) for f in IMPACT_FIELDS if r.get(f)) or _("None")
		r.affected_stages = ", ".join(cstr(r.affected_stages).split("\n")) or None
		if r.status == PENDING:
			r.open_reason = _("Awaiting review / approval")
		elif r.status == APPROVED and cstr(r.actions_required).strip() and not r.actions_complete:
			r.open_reason = _("Actions outstanding")
		if filters.only_open and not r.get("open_reason"):
			continue
		data.append(r)
	return data
