# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""QC Unit Preparation Level moves from free text to a Select of SSPC levels.

Existing values typed as "SP6", "sspc sp-10", "SSPC-SP WJ2" and so on are rewritten to the
matching option so the form saves. Blank values stay blank (the SSPC-SP3 default only applies
to new units). Values that match no level are left as typed and listed in the migrate output.
"""

import re

import frappe

DOCTYPE = "QC Unit"
FIELD = "coat_preparation_level"


def normalise(value, options):
	key = re.sub(r"[^A-Z0-9]", "", (value or "").upper())
	key = key.removeprefix("SSPC").removeprefix("SP")
	for option in options:
		if key == re.sub(r"[^A-Z0-9]", "", option.upper()).removeprefix("SSPCSP"):
			return option
	return None


def execute():
	frappe.reload_doc("shop_qc", "doctype", "qc_unit")
	options = [o for o in (frappe.get_meta(DOCTYPE).get_field(FIELD).options or "").split("\n") if o]
	unmatched = []
	for name, value in frappe.get_all(
		DOCTYPE, filters={FIELD: ("not in", ("", None))}, fields=["name", FIELD], as_list=True
	):
		if value in options:
			continue
		match = normalise(value, options)
		if match:
			frappe.db.set_value(DOCTYPE, name, FIELD, match, update_modified=False)
		else:
			unmatched.append(f"{name}: {value}")
	if unmatched:
		print(f"QC Unit Preparation Level values with no SSPC match (fix by hand): {', '.join(unmatched)}")
