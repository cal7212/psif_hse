# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import json
from pathlib import Path

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "HPU Build"
SYNC_ROLE = "HPU Sync"

DEFAULT_STAGES = [
	# name, sequence, required, hold point, final
	("Frame & Weld", 10, 1, 0, 0),
	("Mechanical Assembly", 20, 1, 1, 0),
	("Hydraulic Plumbing", 30, 1, 1, 0),
	("Electrical & Controls", 40, 1, 1, 0),
	("Flush & Cleanliness", 50, 1, 1, 0),
	("Pressure & Function Test", 60, 1, 1, 0),
	("Final Release", 70, 1, 1, 1),
]


def get_custom_fields():
	# severity, interim_control, verified_by, verification_date and corrective_action
	# on Non Conformance are created by the Asset Inspection module and reused here.
	return {
		"Non Conformance": [
			{
				"fieldname": "hpu_section",
				"label": "HPU Build Inspection",
				"fieldtype": "Section Break",
				"insert_after": "housekeeping_reinspection",
				"depends_on": "eval:doc.hpu_unit || doc.hpu_build_inspection",
			},
			{
				"fieldname": "hpu_unit",
				"label": "HPU Unit",
				"fieldtype": "Link",
				"options": "HPU Unit",
				"insert_after": "hpu_section",
				"in_standard_filter": 1,
			},
			{
				"fieldname": "hpu_build_inspection",
				"label": "HPU Build Inspection",
				"fieldtype": "Link",
				"options": "HPU Build Inspection",
				"insert_after": "hpu_unit",
				"read_only": 1,
			},
			{
				"fieldname": "hpu_column_break",
				"fieldtype": "Column Break",
				"insert_after": "hpu_build_inspection",
			},
			{
				"fieldname": "hpu_reinspection",
				"label": "HPU Re-inspection",
				"fieldtype": "Link",
				"options": "HPU Build Inspection",
				"insert_after": "hpu_column_break",
				"read_only": 1,
			},
		],
	}


def make_custom_fields():
	fields = get_custom_fields()
	for rows in fields.values():
		for row in rows:
			row["module"] = MODULE
	create_custom_fields(fields, update=True)


def make_role():
	if not frappe.db.exists("Role", SYNC_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": SYNC_ROLE, "desk_access": 0}).insert(
			ignore_permissions=True
		)


def make_default_stages():
	if frappe.db.count("HPU Build Stage"):
		return  # never overwrite stages the user has edited
	for name, seq, req, hold, final in DEFAULT_STAGES:
		frappe.get_doc(
			{
				"doctype": "HPU Build Stage",
				"stage_name": name,
				"sequence": seq,
				"is_required": req,
				"hold_point": hold,
				"is_final_release": final,
			}
		).insert(ignore_permissions=True)


def create_sample_templates(quality_procedure: str = "HPU Build Inspection"):
	"""Run once by hand:
	bench --site <site> execute hse.hpu_build.install.create_sample_templates
	Creates the Quality Procedure (if missing) and one generic template per default stage.
	Existing templates with the same name are left alone."""
	if not frappe.db.exists("Quality Procedure", quality_procedure):
		frappe.get_doc(
			{
				"doctype": "Quality Procedure",
				"quality_procedure_name": quality_procedure,
			}
		).insert(ignore_permissions=True)

	data = json.loads((Path(__file__).parent / "sample_templates.json").read_text())
	created = []
	for t in data:
		if frappe.db.exists("HPU Build Inspection Template", t["template_name"]):
			continue
		if not frappe.db.exists("HPU Build Stage", t["stage"]):
			continue
		doc = frappe.get_doc(
			{"doctype": "HPU Build Inspection Template", "quality_procedure": quality_procedure, **t}
		)
		doc.insert(ignore_permissions=True)
		created.append(doc.name)
	# No manual commit: `bench execute` and install hooks commit on completion.
	return created


def after_install():
	after_migrate()


def after_migrate():
	make_role()
	make_custom_fields()
	make_default_stages()
