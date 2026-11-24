# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""ISO 9001 8.3.6 / 8.5.6 change review: give existing change orders a Change Type.

Every change order made before this had a Customer or Engineering & Design source, i.e. a design
change. The review fields stay blank on old rows: they were approved under the old process, and
inventing review results for them would not be a true record. Pending rows are reviewed as usual
before they are approved."""

import frappe


def execute():
	count = frappe.db.count("QC Change Order", {"change_type": ("in", ("", None))})
	frappe.db.sql(
		"""update `tabQC Change Order` set change_type = 'Design'
		where ifnull(change_type, '') = ''"""
	)
	print(f"Change Type set to Design on {count} existing change order(s).")
