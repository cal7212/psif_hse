import frappe
from frappe import _

from hse.housekeeping_inspection.utils import update_area_housekeeping_status


def validate(doc, method=None):
	"""Closure gate: a housekeeping-driven Non Conformance cannot be resolved
	until the fix is documented, verified, and re-inspected."""
	if not doc.get("housekeeping_inspection") or doc.status != "Resolved":
		return

	required = {
		"corrective_action": _("Corrective Action"),
		"verified_by": _("Verified By"),
		"verification_date": _("Verification Date"),
		"housekeeping_reinspection": _("Housekeeping Re-inspection"),
	}
	missing = [label for field, label in required.items() if not doc.get(field)]
	if missing:
		frappe.throw(
			_("Cannot resolve this Non Conformance until these are completed: {0}").format(", ".join(missing)),
			title=_("Resolution Blocked"),
		)

	status, docstatus = frappe.db.get_value(
		"Housekeeping Inspection", doc.housekeeping_reinspection, ["status", "docstatus"]
	) or (None, None)
	if docstatus != 1 or status != "Accepted":
		frappe.throw(
			_("Re-inspection {0} must be submitted and Accepted before resolving.").format(
				frappe.bold(doc.housekeeping_reinspection)
			),
			title=_("Resolution Blocked"),
		)


def on_update(doc, method=None):
	if doc.get("housekeeping_area"):
		update_area_housekeeping_status(doc.housekeeping_area)
