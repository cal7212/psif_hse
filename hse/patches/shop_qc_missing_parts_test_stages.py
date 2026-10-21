import frappe


def execute():
	"""Missing parts: test stages (per-PMG or proof test) wait until every part is found.

	Runs once; the flag can be changed on each QC Stage afterwards."""
	for stage in frappe.get_all("QC Stage", filters=[["pmg_test", "=", 1]], pluck="name") + frappe.get_all(
		"QC Stage", filters=[["proof_test", "=", 1]], pluck="name"
	):
		frappe.db.set_value("QC Stage", stage, "requires_all_parts", 1, update_modified=False)
