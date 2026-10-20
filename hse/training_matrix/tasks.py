# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Scheduled jobs for the Training Matrix module."""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from hse.training_matrix import status as st
from hse.training_matrix.matrix import MATRIX, refresh_matrix_status

ALL = "All"


def refresh_all_matrices():
	"""Daily: recalculate Due / Overdue / expiry on every active matrix (TRN-700 §4.9)."""
	for name in frappe.get_all(MATRIX, filters={"active": 1}, pluck="name"):
		try:
			refresh_matrix_status(name)
		except Exception:
			frappe.log_error(title=_("Training matrix refresh failed for {0}").format(name))
	try:
		from hse.training_matrix.notifications import process_overdue

		process_overdue()
	except Exception:
		frappe.log_error(title=_("Training overdue notices failed"))


def write_monthly_snapshot(on_date=None):
	"""1st of the month: store headline training figures so trends survive later updates.

	One Training Metric Snapshot per (department, avenue), plus All rows for each.
	Existing snapshots for the same date are replaced, so the job can be re-run.
	"""
	on_date = getdate(on_date or today())
	refresh_all_matrices()
	rows = frappe.get_all(
		"Employee Training Matrix Item",
		filters={"parenttype": MATRIX, "active": 1, "is_required": 1},
		fields=["parent", "department", "avenue", "status", "qualification", "high_hazard"],
	)
	confirm = frappe.get_all(
		"Employee Training Matrix Item",
		filters={"parenttype": MATRIX, "active": 1, "status": st.CONFIRM},
		fields=["department", "avenue"],
	)
	buckets: dict[tuple[str, str], dict] = {}

	def bucket(dept, avenue):
		return buckets.setdefault(
			(dept, avenue),
			{
				"employees": set(),
				"required": 0,
				"compliant": 0,
				"overdue": 0,
				"due": 0,
				"hh": 0,
				"confirm": 0,
			},
		)

	for r in rows:
		for key in _keys(r):
			b = bucket(*key)
			b["employees"].add(r.parent)
			b["required"] += 1
			b["compliant"] += r.qualification == st.QUALIFIED
			b["overdue"] += r.status == st.OVERDUE
			b["due"] += r.status == st.DUE
			b["hh"] += bool(r.high_hazard and r.status == st.OVERDUE)
	for r in confirm:
		for key in _keys(r):
			bucket(*key)["confirm"] += 1

	frappe.db.delete("Training Metric Snapshot", {"snapshot_date": on_date})
	for (dept, avenue), b in sorted(buckets.items()):
		frappe.get_doc(
			{
				"doctype": "Training Metric Snapshot",
				"snapshot_date": on_date,
				"department": dept,
				"avenue": avenue,
				"employees": len(b["employees"]),
				"required_items": b["required"],
				"compliant_items": b["compliant"],
				"overdue_items": b["overdue"],
				"due_items": b["due"],
				"high_hazard_overdue": b["hh"],
				"confirm_pending": b["confirm"],
				"compliance_pct": round(flt(b["compliant"]) / b["required"] * 100, 1) if b["required"] else 0,
			}
		).insert(ignore_permissions=True)


def _keys(r):
	dept, avenue = r.department or _("No Department"), r.avenue or _("No Avenue")
	return ((dept, avenue), (dept, ALL), (ALL, avenue), (ALL, ALL))
