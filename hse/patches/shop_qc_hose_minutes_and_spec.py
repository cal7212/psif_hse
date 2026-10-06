# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Hose hold times move from seconds to minutes, and hoses get a spec basis.

Old *_sec / hold_time_* columns stay in the database (Frappe does not drop columns), so they
are read here and converted once. Rows that already have a minutes value are left alone.
"""

import frappe

from hse.shop_qc.doctype.qc_inspection.qc_inspection import crimp_status

CONVERSIONS = (
	("QC Hose Assembly", "hold_time_sec", "hold_time_min"),
	("QC Hose Test", "hold_time_spec", "hold_spec_min"),
	("QC Hose Test", "hold_time_actual", "hold_actual_min"),
	("Build Shop", "default_hold_time_sec", "default_hold_time_min"),
)


def execute():
	for doctype, old, new in CONVERSIONS:
		if not (frappe.db.has_column(doctype, old) and frappe.db.has_column(doctype, new)):
			continue
		t = frappe.qb.DocType(doctype)
		(
			frappe.qb.update(t)
			.set(t[new], t[old] / 60)
			.where((t[old] > 0) & ((t[new].isnull()) | (t[new] == 0)))
		).run()

	if frappe.db.has_column("QC Hose Assembly", "spec_basis"):
		frappe.db.set_value(
			"QC Hose Assembly",
			{"spec_basis": ("in", ("", None))},
			"spec_basis",
			"PSIF Standard",
			update_modified=False,
		)
	# Existing test rows: record the basis and the crimp status they were judged against.
	for row in frappe.get_all(
		"QC Hose Test",
		fields=["name", "crimp_min", "crimp_max", "crimp_a", "crimp_b", "spec_basis"],
	):
		values = {"crimp_status": crimp_status(frappe._dict(row))}
		if not row.spec_basis:
			values["spec_basis"] = "PSIF Standard"
		frappe.db.set_value("QC Hose Test", row.name, values, update_modified=False)
