# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Sub-assemblies built on their own work order and tested as part of another unit.

A control panel (or any other separately built item) has its own QC Unit and TrulinX work
order. Installed In links it to the HPU unit it goes into. The HPU's test and final release
stages cannot be completed until each linked sub-assembly has passed its own build checks,
has no open NCR and no missing parts outstanding. The sub-assembly's own test stages are
covered by the HPU test, and it is released when the HPU is released.
"""

import frappe
from frappe import _

REPAIR = "Repair"
HOST_DONE = ("Released", "Shipped")


def get_sub_units(qc_unit: str) -> list[dict]:
	if not qc_unit:
		return []
	return frappe.get_all(
		"QC Unit",
		filters={"installed_in": qc_unit, "status": ("!=", "Cancelled")},
		fields=["name", "trulinx_work_order", "model", "serial_no", "product_type", "status"],
		order_by="name asc",
	)


def tested_with_host(stage) -> bool:
	"""Stages a sub-assembly does not complete itself: testing (covered by the host's test)."""
	return bool(frappe.get_cached_value("QC Stage", stage, "requires_all_parts"))


def build_stages_pending(qc_unit: str) -> list[str]:
	from hse.shop_qc.utils import get_accepted_by_stage, get_stages

	accepted = get_accepted_by_stage(qc_unit)
	return [
		s.name
		for s in get_stages(qc_unit, required_only=True)
		if not s.is_final_release and not tested_with_host(s.name) and s.name not in accepted
	]


def sub_unit_blockers(qc_unit: str) -> list[str]:
	"""Why the linked sub-assemblies are not ready to be tested with this unit."""
	from hse.shop_qc.missing_parts import outstanding
	from hse.shop_qc.utils import count_open_ncs

	problems = []
	for sub in get_sub_units(qc_unit):
		reasons = []
		pending = build_stages_pending(sub.name)
		if pending:
			reasons.append(_("stages not accepted: {0}").format(", ".join(pending)))
		ncs = count_open_ncs(sub.name)
		if ncs:
			reasons.append(_("{0} open NCR(s)").format(ncs))
		parts = outstanding(sub.name)
		if parts:
			reasons.append(_("{0} missing part(s)").format(len(parts)))
		if reasons:
			problems.append(f"{sub.name} ({'; '.join(reasons)})")
	return problems


def check_sub_assemblies(insp) -> None:
	"""Test (All Parts Present) and final release stages need every sub-assembly ready."""
	stage = frappe.get_cached_doc("QC Stage", insp.stage)
	if not (stage.requires_all_parts or stage.is_final_release):
		return
	problems = sub_unit_blockers(insp.qc_unit)
	if problems:
		frappe.throw(
			_("{0} cannot be completed until the sub-assemblies installed in {1} are ready: {2}").format(
				frappe.bold(insp.stage), insp.qc_unit, "; ".join(problems)
			),
			title=_("Sub-Assembly Not Ready"),
		)


def validate_installed_in(doc) -> None:
	if not doc.get("installed_in"):
		return
	if doc.installed_in == doc.name:
		frappe.throw(_("A unit cannot be installed in itself."))
	if doc.get("job_type") == REPAIR or doc.get("parent_qc_unit"):
		frappe.throw(_("Installed In is for new-build sub-assemblies on their own work order."))
	host = frappe.db.get_value(
		"QC Unit",
		doc.installed_in,
		["name", "job_type", "parent_qc_unit", "installed_in", "status"],
		as_dict=True,
	)
	if not host:
		frappe.throw(_("QC Unit {0} does not exist.").format(doc.installed_in))
	if host.job_type == REPAIR or host.parent_qc_unit or host.installed_in:
		frappe.throw(
			_(
				"{0} cannot take sub-assemblies: it is a repair, a hose build or itself a sub-assembly."
			).format(host.name)
		)
	if not doc.is_new() and get_sub_units(doc.name):
		frappe.throw(
			_("{0} has its own sub-assemblies and cannot be installed in another unit.").format(doc.name)
		)


def apply_host_release(qc_unit: str, values: dict, open_ncs: int) -> None:
	"""A sub-assembly is released with its host; until then its test stages are the host's."""
	host = frappe.db.get_value("QC Unit", qc_unit, "installed_in")
	if not host or open_ncs:
		return
	h = frappe.db.get_value("QC Unit", host, ["status", "released_on", "released_by"], as_dict=True)
	if h and h.status in HOST_DONE and h.released_on:
		values.update(status="Released", released_on=h.released_on, released_by=h.released_by)


def refresh_sub_units(qc_unit: str) -> None:
	from hse.shop_qc.utils import update_unit_status

	for sub in get_sub_units(qc_unit):
		update_unit_status(sub.name, update_modified=False)


@frappe.whitelist(methods=["POST"])
def link_sub_assembly(qc_unit: str, sub_unit: str) -> str:
	"""Link an existing QC Unit (e.g. a control panel) as installed in this unit."""
	frappe.has_permission("QC Unit", "read", qc_unit, throw=True)
	sub = frappe.get_doc("QC Unit", sub_unit)
	sub.check_permission("write")
	sub.installed_in = qc_unit
	sub.save()
	return sub.name


@frappe.whitelist()
def get_sub_assembly_info(qc_unit: str) -> dict:
	frappe.has_permission("QC Unit", "read", qc_unit, throw=True)
	return {"sub_units": get_sub_units(qc_unit), "blockers": sub_unit_blockers(qc_unit)}
