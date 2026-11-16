# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""No checklist line requires a photo: clear Requires Photo on every QC Inspection Template line
and every QC Inspection reading (draft, submitted and cancelled). Photos already attached are
kept, and a template line can still be ticked again by hand afterwards."""

import frappe


def execute():
	lines = frappe.db.count("QC Inspection Template Item", {"requires_photo": 1})
	readings = frappe.db.count("QC Inspection Reading", {"requires_photo": 1})
	templates = frappe.get_all(
		"QC Inspection Template Item", {"requires_photo": 1}, pluck="parent", distinct=True
	)
	# Direct updates: a flag change on old records should not bump their modified time or re-run
	# validation on submitted inspections.
	frappe.db.sql("update `tabQC Inspection Template Item` set requires_photo = 0 where requires_photo = 1")
	frappe.db.sql("update `tabQC Inspection Reading` set requires_photo = 0 where requires_photo = 1")
	for name in templates:
		frappe.clear_document_cache("QC Inspection Template", name)
	print(f"Photo no longer required on {lines} template line(s) and {readings} inspection reading(s).")
