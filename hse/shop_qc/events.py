# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from hse.shop_qc.utils import update_unit_status


def validate(doc, method=None):
	"""Closure gate: a QC-inspection Non Conformance cannot be resolved until the
	fix is documented, verified, and an Accepted re-inspection exists."""
	if not doc.get("qc_inspection") or doc.status != "Resolved":
		return

	rework = doc.get("record_type") == "Rework"
	required = {
		"corrective_action": _("Rework Performed") if rework else _("Correction"),
		"verified_by": _("Inspected By"),
		"verification_date": _("Inspected Date"),
		"qc_reinspection": _("QC Re-inspection"),
	}
	missing = [label for field, label in required.items() if not doc.get(field)]
	if missing:
		frappe.throw(
			_("Cannot resolve this {0} until these are completed: {1}").format(
				_("Rework") if rework else _("Non Conformance"), ", ".join(missing)
			),
			title=_("Resolution Blocked"),
		)

	status, docstatus = frappe.db.get_value(
		"QC Inspection", doc.qc_reinspection, ["status", "docstatus"]
	) or (None, None)
	if docstatus != 1 or status != "Accepted":
		frappe.throw(
			_("Re-inspection {0} must be submitted and Accepted before resolving.").format(
				frappe.bold(doc.qc_reinspection)
			),
			title=_("Resolution Blocked"),
		)


def on_update(doc, method=None):
	if doc.get("qc_unit"):
		update_unit_status(doc.qc_unit)
