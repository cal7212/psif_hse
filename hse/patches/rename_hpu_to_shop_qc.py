# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Rename the HPU Build module to Shop QC (runs before model sync).

DocType renames move the tables and update every Link / Table option, child parenttype,
and dynamic link (Version, Comment, File, workspace links). Column renames keep the data
in place so the new JSON finds it. Safe to re-run.
"""

import frappe

MODULES = [("HPU Build", "Shop QC")]
DOCTYPES = [
	("HPU Build Inspection Template Item", "QC Inspection Template Item"),
	("HPU Build Inspection Template", "QC Inspection Template"),
	("HPU Build Inspection Reading", "QC Inspection Reading"),
	("HPU Build Inspection", "QC Inspection"),
	("HPU Build Stage", "QC Stage"),
	("HPU Unit", "QC Unit"),
]
COLUMNS = {
	"QC Inspection": [("hpu_unit", "qc_unit")],
	"Non Conformance": [
		("hpu_unit", "qc_unit"),
		("hpu_build_inspection", "qc_inspection"),
		("hpu_reinspection", "qc_reinspection"),
	],
}
OLD_NC_FIELDS = ["hpu_section", "hpu_unit", "hpu_build_inspection", "hpu_column_break", "hpu_reinspection"]


def has_column(doctype: str, column: str) -> bool:
	# Read the live schema (not the cached meta): tables were just renamed.
	return bool(
		frappe.db.sql(
			"""select 1 from information_schema.columns
			where table_schema = database() and table_name = %s and column_name = %s""",
			(f"tab{doctype}", column),
		)
	)


def move_module(old: str, new: str):
	"""Frappe only renames custom modules, so create the new Module Def and repoint every
	Link to Module Def (DocType, Print Format, Report, Workspace, ...) before removing the old one."""
	if not frappe.db.exists("Module Def", old):
		return
	if not frappe.db.exists("Module Def", new):
		frappe.get_doc({"doctype": "Module Def", "module_name": new, "app_name": "hse"}).insert(
			ignore_permissions=True
		)
	link = {"fieldtype": "Link", "options": "Module Def"}
	fields = [
		(f.parent, f.fieldname)
		for f in frappe.get_all("DocField", filters=link, fields=["parent", "fieldname"])
	] + [
		(f.dt, f.fieldname) for f in frappe.get_all("Custom Field", filters=link, fields=["dt", "fieldname"])
	]
	for parent, fieldname in set(fields):
		meta = frappe.db.get_value("DocType", parent, ["issingle", "is_virtual"], as_dict=True)
		if not meta or meta.issingle or meta.is_virtual or not frappe.db.table_exists(parent):
			continue
		if not has_column(parent, fieldname):
			continue
		t = frappe.qb.DocType(parent)
		frappe.qb.update(t).set(t[fieldname], new).where(t[fieldname] == old).run()
	frappe.db.delete("Module Def", {"name": old})
	frappe.clear_cache()


def execute():
	for old, new in MODULES:
		move_module(old, new)

	for old, new in DOCTYPES:
		if frappe.db.exists("DocType", old) and not frappe.db.exists("DocType", new):
			frappe.rename_doc("DocType", old, new, force=True)
			frappe.db.set_value("DocType", new, "module", "Shop QC")

	for doctype, pairs in COLUMNS.items():
		if not frappe.db.table_exists(doctype):
			continue
		for old, new in pairs:
			if has_column(doctype, old) and not has_column(doctype, new):
				frappe.db.rename_column(doctype, old, new)

	# Old Non Conformance custom fields; after_migrate creates the qc_* replacements.
	# Raw delete so no column is dropped (the data is already in the renamed columns).
	frappe.db.delete("Custom Field", {"dt": "Non Conformance", "fieldname": ("in", OLD_NC_FIELDS)})
	frappe.db.delete("Property Setter", {"doc_type": "Non Conformance", "field_name": ("in", OLD_NC_FIELDS)})
	frappe.clear_cache(doctype="Non Conformance")
