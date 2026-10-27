# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Shop QC workspace: build progress per unit and the Custom Number Card methods.

The quality cards reuse the Quality Metrics functions so the workspace and the
Quality Reviews always calculate the same way.
"""

from pathlib import Path

import frappe
from frappe.utils import add_days, getdate

from hse.quality_metrics import metrics
from hse.shop_qc.utils import get_accepted_by_stage, get_stages

ACTIVE_STATUSES = ("Pending Build", "In Build", "QC Hold", "Ready for Release")
NO_VALUE = "-"


# ---------------------------------------------------------------- build progress
def summarise_progress(stages: list, accepted) -> dict:
	"""Accepted / total stages, percent and the first stage still to pass."""
	names = [s.name for s in stages]
	done = [n for n in names if n in accepted]
	next_stage = next((n for n in names if n not in accepted), None)
	total = len(names)
	return {
		"stages_accepted": len(done),
		"stages_total": total,
		"progress": round(len(done) / total * 100, 1) if total else 0,
		"next_stage": next_stage,
	}


def unit_progress(qc_unit: str) -> dict:
	return summarise_progress(get_stages(qc_unit), get_accepted_by_stage(qc_unit))


def open_missing_parts(units: list[str]) -> dict:
	"""{unit: number of missing parts not yet found}."""
	if not units:
		return {}
	rows = frappe.get_all(
		"QC Missing Part",
		filters={"parenttype": "QC Unit", "parent": ["in", units], "found": 0},
		pluck="parent",
	)
	out = {}
	for unit in rows:
		out[unit] = out.get(unit, 0) + 1
	return out


# ---------------------------------------------------------------- number cards
def _check_access():
	frappe.has_permission("QC Unit", "read", throw=True)


def _window(days: int):
	end = getdate()
	return add_days(end, -(days - 1)), end


def _card(value, fieldtype: str = "Int", route=None, route_options=None):
	if value is None:
		# Nothing to measure in the period: show a dash rather than a misleading 0%.
		return NO_VALUE
	out = {"value": value, "fieldtype": fieldtype}
	if route:
		out["route"] = route
	if route_options:
		out["route_options"] = route_options
	return out


@frappe.whitelist()
def first_pass_yield(filters: str | dict | list | None = None):
	"""Released units in the last 90 days with no rejected inspection."""
	_check_access()
	value, _detail = metrics.hpu_first_pass_yield(*_window(90))
	return _card(value, "Percent", ["query-report", "QC Unit Build Status"])


@frappe.whitelist()
def units_released(filters: str | dict | list | None = None):
	_check_access()
	start, _end = _window(30)
	value, _detail = metrics.hpu_units_released(*_window(30))
	return _card(
		value,
		route=["List", "QC Unit"],
		route_options={"released_on": [">=", str(start)]},
	)


@frappe.whitelist()
def rejected_inspections(filters: str | dict | list | None = None):
	_check_access()
	start, _end = _window(30)
	value, _detail = metrics.hpu_stage_rejections(*_window(30))
	return _card(
		value,
		route=["List", "QC Inspection"],
		route_options={"status": "Rejected", "docstatus": 1, "inspection_date": [">=", str(start)]},
	)


@frappe.whitelist()
def shipped_before_release(filters: str | dict | list | None = None):
	_check_access()
	value, _detail = metrics.hpu_shipped_before_release(*_window(90))
	return _card(value, route=["List", "QC Unit"], route_options={"qc_flag": ["is", "set"]})


@frappe.whitelist()
def critical_ncrs_over_7_days(filters: str | dict | list | None = None):
	frappe.has_permission("Non Conformance", "read", throw=True)
	value, _detail = metrics.nc_open_critical_over_7_days(None, None)
	return _card(
		value,
		route=["List", "Non Conformance"],
		route_options={"status": "Open", "severity": "Critical"},
	)


@frappe.whitelist()
def units_with_missing_parts(filters: str | dict | list | None = None):
	"""Active units with at least one missing part not yet found."""
	_check_access()
	units = frappe.get_all("QC Unit", filters={"status": ["in", ACTIVE_STATUSES]}, pluck="name")
	value = len(open_missing_parts(units))
	return _card(value, route=["query-report", "QC Unit Build Status"], route_options={"missing_parts": 1})


@frappe.whitelist()
def active_units() -> list[dict]:
	"""Active QC Units for the workspace block: WO (unit ID), model, status and next stage."""
	_check_access()
	units = frappe.get_list(
		"QC Unit",
		filters={"status": ["in", ACTIVE_STATUSES]},
		fields=["name", "model", "status"],
		order_by="name asc",
	)
	rank = {s: i for i, s in enumerate(("QC Hold", "In Build", "Ready for Release", "Pending Build"))}
	for u in units:
		u.next_stage = unit_progress(u.name)["next_stage"]
	units.sort(key=lambda u: (rank.get(u.status, len(rank)), u.name))
	return units


# ---------------------------------------------------------------- workspace blocks
BLOCKS_DIR = Path(__file__).parent / "workspace_blocks"
WORKSPACE_BLOCKS = {
	# Custom HTML Block name: file stem in workspace_blocks/
	"Shop QC Active Units": "active_units",
}


def make_workspace_blocks():
	"""Create or refresh the Custom HTML Blocks used by the Shop QC workspace.

	Custom HTML Block is not synced from app files, so it is kept here and rewritten on migrate.
	"""
	for name, stem in WORKSPACE_BLOCKS.items():
		values = {
			"html": (BLOCKS_DIR / f"{stem}.html").read_text(),
			"script": (BLOCKS_DIR / f"{stem}.js").read_text(),
			"style": (BLOCKS_DIR / f"{stem}.css").read_text(),
			"private": 0,
		}
		if frappe.db.exists("Custom HTML Block", name):
			doc = frappe.get_doc("Custom HTML Block", name)
			if all(doc.get(k) == v for k, v in values.items()):
				continue
			doc.update(values)
			doc.save(ignore_permissions=True)
		else:
			doc = frappe.new_doc("Custom HTML Block")
			doc.update(values)
			doc.insert(ignore_permissions=True, set_name=name)
