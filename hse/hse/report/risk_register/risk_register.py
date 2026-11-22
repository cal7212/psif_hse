# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Risk Register: every hazard on the risk assessments in force, with its initial and residual
risk, highest residual risk first (ISO 45001 6.1.2)."""

import frappe
from frappe import _

from hse.hse.doctype.risk_assessment.risk_assessment import RATING_ORDER

RA = "Risk Assessment"


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	def col(label, fieldname, fieldtype="Data", width=120, **kw):
		return {"label": _(label), "fieldname": fieldname, "fieldtype": fieldtype, "width": width, **kw}

	return [
		col("Assessment", "risk_assessment", "Link", 140, options=RA),
		col("Activity / Area", "title", width=200),
		col("Rev", "revision", "Int", 50),
		col("Location", "location", "Link", 130, options="Location"),
		col("Department", "department", "Link", 130, options="Department"),
		col("Row", "idx", "Int", 50),
		col("Category", "hazard_category", width=150),
		col("Hazard", "hazard", width=240),
		col("Existing Controls", "existing_controls", width=200),
		col("Initial", "initial_score", "Int", 65),
		col("Initial Rating", "initial_rating", width=95),
		col("Control Type", "control_type", width=150),
		col("Additional Controls", "additional_controls", width=200),
		col("Residual", "residual_score", "Int", 75),
		col("Residual Rating", "residual_rating", width=105),
		col("Next Review", "next_review_date", "Date", 100),
		col("Status", "status", width=90),
	]


def get_data(filters):
	ra = frappe.qb.DocType(RA)
	hz = frappe.qb.DocType("Risk Assessment Hazard")
	q = (
		frappe.qb.from_(ra)
		.join(hz)
		.on((hz.parent == ra.name) & (hz.parenttype == RA) & (hz.parentfield == "hazards"))
		.select(
			ra.name.as_("risk_assessment"),
			ra.title,
			ra.revision,
			ra.location,
			ra.department,
			ra.next_review_date,
			ra.status,
			hz.idx,
			hz.hazard_category,
			hz.hazard,
			hz.existing_controls,
			hz.initial_score,
			hz.initial_rating,
			hz.control_type,
			hz.additional_controls,
			hz.residual_score,
			hz.residual_rating,
		)
		.where(ra.docstatus < 2)
	)
	if filters.include_drafts:
		q = q.where(ra.status.isin(["Active", "Draft"]))
	else:
		q = q.where(ra.status == "Active")
	for field in ("company", "department", "assessment_type"):
		if filters.get(field):
			q = q.where(ra[field] == filters.get(field))
	if filters.hazard_category:
		q = q.where(hz.hazard_category == filters.hazard_category)
	if filters.location:
		lft, rgt = frappe.db.get_value("Location", filters.location, ["lft", "rgt"])
		children = frappe.get_all("Location", filters={"lft": [">=", lft], "rgt": ["<=", rgt]}, pluck="name")
		q = q.where(ra.location.isin(children))
	rows = q.run(as_dict=True)
	if filters.min_residual_rating:
		floor = RATING_ORDER.get(filters.min_residual_rating, 0)
		rows = [r for r in rows if RATING_ORDER.get(r.residual_rating or "", 0) >= floor]
	rows.sort(key=lambda r: (-(r.residual_score or 0), -(r.initial_score or 0), r.risk_assessment, r.idx))
	return rows
