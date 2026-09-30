import frappe
from frappe import _

from hse.asset_inspection.utils import update_asset_safety_status


def validate(doc, method=None):
	"""Closure gate: an inspection-driven Non Conformance cannot be resolved
	until the fix is documented, verified, and re-inspected."""
	if not doc.get("asset_inspection") or doc.status != "Resolved":
		return

	required = {
		"corrective_action": _("Corrective Action"),
		"verified_by": _("Verified By"),
		"verification_date": _("Verification Date"),
		"reinspection": _("Re-inspection"),
	}
	missing = [label for field, label in required.items() if not doc.get(field)]
	if missing:
		frappe.throw(
			_("Cannot resolve this Non Conformance until these are completed: {0}").format(
				", ".join(missing)
			),
			title=_("Resolution Blocked"),
		)

	status, docstatus = frappe.db.get_value(
		"Asset Inspection", doc.reinspection, ["status", "docstatus"]
	) or (None, None)
	if docstatus != 1 or status != "Accepted":
		frappe.throw(
			_("Re-inspection {0} must be submitted and Accepted before resolving.").format(
				frappe.bold(doc.reinspection)
			),
			title=_("Resolution Blocked"),
		)


def on_update(doc, method=None):
	if doc.get("asset"):
		update_asset_safety_status(doc.asset)
