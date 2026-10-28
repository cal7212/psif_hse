"""Copy ERPNext Non Conformance records to the HSE Nonconformance Report doctype.

Records keep their names (QA-NC-/QA-RW-), owners and timestamps, so every Link value that already
points at them stays valid. CAPA Related NCR rows, attachments, comments, assignments, shares,
tags and versions are moved to the new record. The ERPNext records stay behind as a read-only
archive; new inserts there are blocked by hse.quality_metrics.ncr.block_legacy_insert.
"""

import frappe
from frappe.query_builder import DocType

OLD = "Non Conformance"
NEW = "Nonconformance Report"

# (doctype, doctype field, name field) pairs that are not Dynamic Links.
PLAIN_REFERENCES = (
	("File", "attached_to_doctype", "attached_to_name"),
	("Version", "ref_doctype", "docname"),
	("Notification Log", "document_type", "document_name"),
	("Document Follow", "ref_doctype", "ref_docname"),
)


def execute():
	if not frappe.db.table_exists(OLD) or not frappe.db.table_exists(NEW):
		return
	names = copy_records()
	if not names:
		return
	move_child_rows()
	move_references(names)


def copy_records() -> list[str]:
	old = DocType(OLD)
	names = frappe.qb.from_(old).select(old.name).run(pluck=True)
	existing = set(frappe.get_all(NEW, pluck="name"))
	todo = [name for name in names if name not in existing]
	if todo:
		new_columns = set(frappe.db.get_table_columns(NEW))
		columns = [c for c in frappe.db.get_table_columns(OLD) if c in new_columns]
		rows = frappe.qb.from_(old).select(*[old[c] for c in columns]).where(old.name.isin(todo)).run()
		frappe.db.bulk_insert(NEW, columns, rows)
	return names


def move_child_rows() -> None:
	for child in frappe.get_all(
		"DocField",
		filters={"parent": NEW, "fieldtype": ["in", ["Table", "Table MultiSelect"]]},
		pluck="options",
	):
		table = DocType(child)
		frappe.qb.update(table).set(table.parenttype, NEW).where(table.parenttype == OLD).run()


def move_references(names: list[str]) -> None:
	pairs = list(PLAIN_REFERENCES)
	for meta_doctype in ("DocField", "Custom Field"):
		parent = "parent" if meta_doctype == "DocField" else "dt"
		for row in frappe.get_all(
			meta_doctype, filters={"fieldtype": "Dynamic Link"}, fields=[parent, "fieldname", "options"]
		):
			pairs.append((row[parent], row.options, row.fieldname))

	for doctype, doctype_field, name_field in pairs:
		if doctype in (OLD, NEW) or not doctype_field or not frappe.db.table_exists(doctype):
			continue
		columns = set(frappe.db.get_table_columns(doctype))
		if doctype_field not in columns or name_field not in columns:
			continue
		table = DocType(doctype)
		(
			frappe.qb.update(table)
			.set(table[doctype_field], NEW)
			.where((table[doctype_field] == OLD) & table[name_field].isin(names))
			.run()
		)
