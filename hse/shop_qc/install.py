# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import json
from pathlib import Path

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Shop QC"
SYNC_ROLE = "HPU Sync"

SHOPS = [
	# name, inspection prefix, certificate title
	("HPU", "HBI", "HPU Quality Control Certificate"),
	("Small Assembly", "SAI", "Small Assembly Quality Control Certificate"),
	("Hose", "HOS", "Hose Assembly Test Certificate"),
]

FAILURE_CAUSES = [
	"Contamination",
	"Seal / O-ring Failure",
	"Wear",
	"Overpressure",
	"Improper Installation or Use",
	"Manufacturing Defect",
	"Hose Abrasion / External Damage",
	"Fitting Leak",
	"Electrical / Motor Failure",
	"Pump Failure",
	"Valve / Cartridge Failure",
	"No Fault Found",
	"Other",
]

# Starting points only; edit them in QC Stage. A set is created only when that shop/job type has no stages.
# name, sequence, required, hold point, final, per-hose test
DEFAULT_STAGES = {
	("HPU", "New Build"): [
		("Frame & Weld", 10, 1, 0, 0, 0),
		("Mechanical Assembly", 20, 1, 1, 0, 0),
		("Hydraulic Plumbing", 30, 1, 1, 0, 0),
		("Electrical & Controls", 40, 1, 1, 0, 0),
		("Flush & Cleanliness", 50, 1, 1, 0, 0),
		("Pressure & Function Test", 60, 1, 1, 0, 0),
		("Final Release", 70, 1, 1, 1, 0),
	],
	("Small Assembly", "New Build"): [
		("SA - Component & Assembly Check", 10, 1, 0, 0, 0),
		("SA - Electrical & Controls", 20, 0, 0, 0, 0),
		("SA - Flush & Cleanliness", 30, 1, 1, 0, 0),
		("SA - Pressure & Function Test", 40, 1, 1, 0, 0),
		("SA - Final Release", 50, 1, 1, 1, 0),
	],
	("Hose", "New Build"): [
		("Hose - Fabrication Check", 10, 1, 0, 0, 0),
		("Hose - Crimp & Pressure Test", 20, 1, 1, 0, 1),
		("Hose - Final Release", 30, 1, 1, 1, 0),
	],
	(None, "Repair"): [
		("Repair - Receiving & As-Received", 10, 1, 0, 0, 0),
		("Repair - Evaluation", 20, 1, 0, 0, 0),
		("Repair - Repair Work", 30, 1, 1, 0, 0),
		("Repair - Test", 40, 1, 1, 0, 1),
		("Repair - Final Release", 50, 1, 1, 1, 0),
	],
}


def get_custom_fields():
	# severity, interim_control, verified_by, verification_date and corrective_action
	# on Non Conformance are created by the Asset Inspection module and reused here.
	return {
		"Non Conformance": [
			{
				"fieldname": "qc_section",
				"label": "Shop QC",
				"fieldtype": "Section Break",
				"insert_after": "housekeeping_reinspection",
				"depends_on": "eval:doc.qc_unit || doc.qc_inspection",
			},
			{
				"fieldname": "qc_unit",
				"label": "QC Unit",
				"fieldtype": "Link",
				"options": "QC Unit",
				"insert_after": "qc_section",
				"in_standard_filter": 1,
			},
			{
				"fieldname": "qc_inspection",
				"label": "QC Inspection",
				"fieldtype": "Link",
				"options": "QC Inspection",
				"insert_after": "qc_unit",
				"read_only": 1,
			},
			{
				"fieldname": "qc_column_break",
				"fieldtype": "Column Break",
				"insert_after": "qc_inspection",
			},
			{
				"fieldname": "qc_reinspection",
				"label": "QC Re-inspection",
				"fieldtype": "Link",
				"options": "QC Inspection",
				"insert_after": "qc_column_break",
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


def make_shops():
	for name, prefix, title in SHOPS:
		if frappe.db.exists("Build Shop", name):
			continue
		frappe.get_doc(
			{
				"doctype": "Build Shop",
				"shop_name": name,
				"inspection_prefix": prefix,
				"certificate_title": title,
			}
		).insert(ignore_permissions=True)


def make_failure_causes():
	for cause in FAILURE_CAUSES:
		if not frappe.db.exists("QC Failure Cause", cause):
			frappe.get_doc({"doctype": "QC Failure Cause", "failure_cause": cause}).insert(
				ignore_permissions=True
			)


def make_default_stages():
	for (shop, job_type), stages in DEFAULT_STAGES.items():
		if shop and not frappe.db.exists("Build Shop", shop):
			continue
		if frappe.db.exists("QC Stage", {"shop": shop or ("is", "not set"), "job_type": job_type}):
			continue  # never overwrite or re-add stages the user has edited or deleted
		for name, seq, req, hold, final, hose in stages:
			if frappe.db.exists("QC Stage", name):
				continue
			frappe.get_doc(
				{
					"doctype": "QC Stage",
					"stage_name": name,
					"sequence": seq,
					"shop": shop,
					"job_type": job_type,
					"is_required": req,
					"hold_point": hold,
					"is_final_release": final,
					"hose_test": hose,
				}
			).insert(ignore_permissions=True)


def create_sample_templates(quality_procedure: str = "QC Inspection"):
	"""Run once by hand:
	bench --site <site> execute hse.shop_qc.install.create_sample_templates
	Creates the Quality Procedure (if missing) and sample templates for the default stages.
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
		if frappe.db.exists("QC Inspection Template", t["template_name"]):
			continue
		if not frappe.db.exists("QC Stage", t["stage"]):
			continue
		doc = frappe.get_doc(
			{"doctype": "QC Inspection Template", "quality_procedure": quality_procedure, **t}
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
	make_shops()
	make_failure_causes()
	make_default_stages()
