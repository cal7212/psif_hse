# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Create a Module Def for every module in modules.txt.

`bench install-app` does this, but `bench migrate` only creates one when it syncs a DocType
in that module. A module with no DocTypes (Quality Metrics) would otherwise never get one,
and Custom Fields that set `module` fail link validation.
"""

import frappe


def ensure_module_defs():
	for module in frappe.get_module_list("hse"):
		if not frappe.db.exists("Module Def", module):
			frappe.get_doc({"doctype": "Module Def", "module_name": module, "app_name": "hse"}).insert(
				ignore_permissions=True
			)
