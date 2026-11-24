# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

"""Change review on QC Unit change orders: ISO 9001 8.3.6 and 8.5.6.

8.3.6 (design and development changes) and 8.5.6 (control of changes in production) both ask
that a change is reviewed and controlled so it does not hurt conformity, and that the records
show the change, the review results, who authorised it and the actions taken to prevent adverse
impact. On each QC Change Order row that maps to:

- the change itself ............ Change Type, Description, From / To Rev, Change Order Document
- the review results ........... impact boxes, Review Results, Reviewed By / On
- the authorisation ............ Status = Approved, Approved By / On, Approval Reference
- actions against adverse impact Affected Stages (re-inspection), Actions Required,
                                 Actions Complete, Actions Verified By / On

Called from QC Unit.validate_change_orders (per row) and from QC Inspection's final release check.
"""

import frappe
from frappe import _
from frappe.utils import cstr, now_datetime

APPROVED = "Approved"
PENDING = "Pending"
CUSTOMER = "Customer"
DESIGN = "Design"
PRODUCTION = "Production"
APPROVER_ROLES = ("Quality Manager", "Manufacturing Manager", "System Manager")

IMPACT_FIELDS = (
	"impact_function",
	"impact_safety",
	"impact_customer",
	"impact_purchasing",
	"impact_other_units",
	"impact_delivered",
)
# Frozen once approved: the record of what was reviewed and authorised.
REVIEW_LOCKED_FIELDS = ("change_type", "description", "review_results", "actions_required", *IMPACT_FIELDS)


def default_change_type(source) -> str:
	return PRODUCTION if source == PRODUCTION else DESIGN


def has_impact(row) -> bool:
	return any(row.get(f) for f in IMPACT_FIELDS)


def is_approver() -> bool:
	return bool(set(frappe.get_roles()) & set(APPROVER_ROLES))


def validate_row(row, prev, approving: bool):
	"""Review stamps, approval prerequisites and action verification for one change order row.
	`prev` is the row as last saved (or None); `approving` is True when it is being approved now."""
	row.change_type = row.change_type or default_change_type(row.source)
	row.review_results = cstr(row.review_results).strip() or None
	row.actions_required = cstr(row.actions_required).strip() or None
	set_review_stamp(row, prev)
	if approving:
		check_ready_to_approve(row)
	set_action_verification(row, prev)


def set_review_stamp(row, prev):
	"""Reviewed By / On follow whoever last wrote the review results."""
	if not row.review_results:
		row.reviewed_by = row.reviewed_on = None
	elif not prev or cstr(prev.review_results).strip() != row.review_results or not row.reviewed_by:
		row.reviewed_by = frappe.session.user
		row.reviewed_on = now_datetime()


def check_ready_to_approve(row):
	missing = []
	if not row.change_type:
		missing.append(_(row.meta.get_label("change_type")))
	if not row.review_results:
		missing.append(_(row.meta.get_label("review_results")))
	if has_impact(row) and not row.actions_required:
		missing.append(_(row.meta.get_label("actions_required")))
	if (row.source == CUSTOMER or row.impact_customer) and not cstr(row.approval_reference).strip():
		missing.append(_(row.meta.get_label("approval_reference")))
	if missing:
		frappe.throw(
			_("Change order {0}: complete the change review before approving it: {1}").format(
				frappe.bold(row.co_no), ", ".join(missing)
			),
			title=_("Change Review Incomplete"),
		)


def set_action_verification(row, prev):
	was_complete = bool(prev and prev.actions_complete)
	if row.status != APPROVED:
		row.actions_complete = 0  # actions are verified against an approved change only
	elif bool(row.actions_complete) != was_complete and not is_approver():
		frappe.throw(
			_("Only a {0} can mark the actions on change order {1} complete or reopen them.").format(
				" / ".join(_(r) for r in APPROVER_ROLES), frappe.bold(row.co_no)
			)
		)
	if not row.actions_complete:
		row.actions_verified_by = row.actions_verified_on = None
	elif not was_complete or not row.actions_verified_by:
		row.actions_verified_by = frappe.session.user
		row.actions_verified_on = now_datetime()


def after_approval(unit, row):
	"""Prompts the approver about knock-on effects the review flagged."""
	if row.impact_other_units and unit.name and not unit.is_new():
		from hse.shop_qc.multi_unit import get_order_units

		others = [u.name for u in get_order_units(unit) if u.name != unit.name and u.status != "Cancelled"]
		if others:
			frappe.msgprint(
				_(
					"Change order {0} affects other units. Add it to these units of the same order as well: {1}"
				).format(frappe.bold(row.co_no), ", ".join(others)),
				indicator="orange",
				alert=True,
			)
	if row.impact_delivered:
		frappe.msgprint(
			_(
				"Change order {0} affects product already shipped. Record the containment or customer notice in Actions Required, or raise a Nonconformance Report."
			).format(frappe.bold(row.co_no)),
			indicator="orange",
			alert=True,
		)


def open_change_orders(qc_unit: str) -> list[str]:
	"""Change orders that stop final release: still Pending, or Approved with actions outstanding."""
	rows = frappe.get_all(
		"QC Change Order",
		filters={"parenttype": "QC Unit", "parent": qc_unit, "status": ("in", (PENDING, APPROVED))},
		fields=["co_no", "status", "actions_required", "actions_complete"],
		order_by="idx asc",
	)
	blocked = []
	for r in rows:
		if r.status == PENDING:
			blocked.append(_("{0} (pending approval)").format(r.co_no))
		elif cstr(r.actions_required).strip() and not r.actions_complete:
			blocked.append(_("{0} (actions not complete)").format(r.co_no))
	return blocked


def check_release(qc_unit: str):
	blocked = open_change_orders(qc_unit)
	if blocked:
		frappe.throw(
			_("QC Unit {0} has open change orders. Close them before final release: {1}").format(
				frappe.bold(qc_unit), ", ".join(blocked)
			),
			title=_("Release Blocked"),
		)
