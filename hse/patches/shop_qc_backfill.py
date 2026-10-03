# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Existing HPU records become HPU shop / New Build / Power Unit (runs after model sync)."""

import frappe

from hse.shop_qc.install import make_failure_causes, make_shops


def execute():
	make_shops()
	make_failure_causes()

	frappe.db.sql("""update `tabQC Unit` set shop='HPU' where ifnull(shop, '')=''""")
	frappe.db.sql("""update `tabQC Unit` set job_type='New Build' where ifnull(job_type, '')=''""")
	frappe.db.sql("""update `tabQC Unit` set product_type='Power Unit' where ifnull(product_type, '')=''""")
	frappe.db.sql(
		"""update `tabQC Unit` u set hose_count=(select count(*) from `tabQC Hose Assembly` h
		where h.parent=u.name and h.parenttype='QC Unit')"""
	)

	# Every stage that existed before shops were introduced belongs to the HPU new-build line.
	frappe.db.sql(
		"""update `tabQC Stage` set shop='HPU', job_type='New Build'
		where ifnull(shop, '')='' and ifnull(job_type, '') in ('', 'New Build')"""
	)

	frappe.db.sql(
		"""update `tabQC Inspection` i join `tabQC Unit` u on u.name=i.qc_unit
		set i.shop=u.shop, i.product_type=u.product_type, i.job_type=u.job_type
		where ifnull(i.shop, '')=''"""
	)

	# Replaced by "Power Unit QC Certificate"
	if frappe.db.exists("Print Format", "HPU QC Certificate"):
		frappe.delete_doc("Print Format", "HPU QC Certificate", force=True, ignore_permissions=True)
