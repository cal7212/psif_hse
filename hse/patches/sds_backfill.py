import frappe


def execute():
	"""Backfill fields added when SDS moved from a custom DocType into the HSE app."""
	if not frappe.db.has_column("SDS", "status"):
		return
	frappe.db.sql("update `tabSDS` set status = 'Active' where ifnull(status, '') = ''")
	frappe.db.sql("update `tabSDS` set title = trim(product_name) where ifnull(title, '') = ''")
	frappe.db.sql("update `tabSDS` set upc = null where upc in ('0', '')")
	# SDS is no longer submittable; keep any submitted records editable as drafts.
	frappe.db.sql("update `tabSDS` set docstatus = 0 where docstatus = 1")
