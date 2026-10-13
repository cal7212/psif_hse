import frappe

from hse.shop_qc.install import REPAIR_SHOP, make_shops


def execute():
	"""Repair becomes its own shop with the Repair Evaluation and Repair Costing tabs.

	Costing defaults (burden, freight, expendables, margin, labor rates) are left blank
	for the shop to fill in on Build Shop "Repair"."""
	make_shops()
	frappe.db.set_value("Build Shop", REPAIR_SHOP, "is_repair_shop", 1, update_modified=False)
