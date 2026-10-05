# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Turn on the per-PMG test for the power unit test stages, and copy each power unit's
single motor HP / pump type into PMG-1. Safe to re-run."""

import frappe

from hse.shop_qc.doctype.qc_unit.qc_unit import PUMP_TYPES
from hse.shop_qc.install import PMG_TEST_STAGES


def execute():
	for stage in PMG_TEST_STAGES:
		if frappe.db.exists("QC Stage", stage):
			frappe.db.set_value("QC Stage", stage, "pmg_test", 1, update_modified=False)

	units = frappe.get_all(
		"QC Unit",
		filters={"product_type": "Power Unit"},
		fields=["name", "motor_hp", "pump_type", "voltage", "phase", "hz"],
	)
	for u in units:
		if not (u.motor_hp or u.pump_type):
			continue
		if frappe.db.exists("QC Pump Motor Group", {"parenttype": "QC Unit", "parent": u.name}):
			continue
		frappe.get_doc(
			{
				"doctype": "QC Pump Motor Group",
				"parenttype": "QC Unit",
				"parentfield": "pump_motor_groups",
				"parent": u.name,
				"idx": 1,
				"pmg_tag": "PMG-1",
				"motor_hp": u.motor_hp,
				"pump_type": u.pump_type if u.pump_type in PUMP_TYPES else None,
				"motor_voltage": u.voltage,
				"motor_phase": u.phase,
				"motor_hz": u.hz,
				"notes": None if u.pump_type in PUMP_TYPES or not u.pump_type else f"Pump type: {u.pump_type}",
			}
		).db_insert()
		frappe.db.set_value("QC Unit", u.name, "pmg_count", 1, update_modified=False)
