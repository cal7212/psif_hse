import frappe


def execute():
	"""Fill the derived status_label from is_recordable on existing reports."""
	frappe.db.sql(
		"""update `tabInjury_Illness Report`
		set status_label = if(is_recordable = 1, 'checked', 'unchecked')"""
	)
