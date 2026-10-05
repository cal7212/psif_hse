# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""PSIF System Construction Test Record: add the HPU Coating and Pre-Test Preparation stages,
turn on the proof test and coating record flags, and refresh the unused sample templates.
Safe to re-run."""

import frappe

from hse.shop_qc.install import (
	COATING_STAGES,
	DEFAULT_STAGES,
	PROOF_TEST_STAGES,
	create_sample_templates,
)

NEW_HPU_STAGES = ("Coating", "Pre-Test Preparation")


def execute():
	if frappe.db.exists("Build Shop", "HPU"):
		for name, seq, req, hold, final, hose in DEFAULT_STAGES[("HPU", "New Build")]:
			if name in NEW_HPU_STAGES and not frappe.db.exists("QC Stage", name):
				frappe.get_doc(
					{
						"doctype": "QC Stage",
						"stage_name": name,
						"sequence": seq,
						"shop": "HPU",
						"job_type": "New Build",
						"is_required": req,
						"hold_point": hold,
						"is_final_release": final,
						"hose_test": hose,
						"coating_record": 1 if name in COATING_STAGES else 0,
					}
				).insert(ignore_permissions=True)
	for flag, stages in (("proof_test", PROOF_TEST_STAGES), ("coating_record", COATING_STAGES)):
		for stage in stages:
			if frappe.db.exists("QC Stage", stage):
				frappe.db.set_value("QC Stage", stage, flag, 1, update_modified=False)
	create_sample_templates(update_unused=True)
