# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Safety versus maintenance for asset inspections and maintenance tasks.

Rule:
- An inspection template's Purpose, when set, decides (Safety or Maintenance). This is how the
  forklift daily pre-shift check counts as safety (OSHA-required pre-use inspection) although the
  forklifts are in a non-safety asset category.
- Otherwise the asset category decides: "Safety Equipment" (HSE Asset Settings, Safety Asset
  Category) is safety; every other category is maintenance.

Safety items show on the HSE Dashboard and in the Safety pillar; maintenance items on the
Maintenance Dashboard. The combined figures (asset_inspection_on_time_pct and its Equipment
Inspections goal) still count both.
"""

import frappe

SAFETY, MAINTENANCE = "Safety", "Maintenance"
DEFAULT_SAFETY_CATEGORY = "Safety Equipment"
LOG = "Asset Maintenance Log"
TEMPLATE = "Asset Inspection Template"


def safety_category() -> str:
	try:
		value = frappe.db.get_single_value("HSE Asset Settings", "safety_asset_category")
	except Exception:
		value = None
	return value or DEFAULT_SAFETY_CATEGORY


def template_purposes() -> dict[str, str]:
	"""{template: "Safety" | "Maintenance"} for templates with a Purpose set."""
	if not frappe.db.has_column(TEMPLATE, "inspection_purpose"):
		return {}
	rows = frappe.get_all(
		TEMPLATE,
		filters={"inspection_purpose": ["in", [SAFETY, MAINTENANCE]]},
		fields=["name", "inspection_purpose"],
	)
	return {r.name: r.inspection_purpose for r in rows}


def purpose_of(asset_category: str | None, template: str | None = None, overrides: dict | None = None) -> str:
	overrides = template_purposes() if overrides is None else overrides
	if template and template in overrides:
		return overrides[template]
	return SAFETY if asset_category and asset_category == safety_category() else MAINTENANCE


def classify_logs(rows: list) -> dict[str, str]:
	"""{log name: purpose} for Asset Maintenance Log rows carrying name, asset_maintenance, task."""
	if not rows:
		return {}
	ams = {r.asset_maintenance for r in rows if r.get("asset_maintenance")}
	categories = dict(
		frappe.get_all(
			"Asset Maintenance",
			filters={"name": ["in", list(ams)]},
			fields=["name", "asset_category"],
			as_list=True,
		)
	)
	tasks = {r.task for r in rows if r.get("task")}
	templates = {}
	if tasks and frappe.db.has_column("Asset Maintenance Task", "inspection_template"):
		templates = dict(
			frappe.get_all(
				"Asset Maintenance Task",
				filters={"name": ["in", list(tasks)]},
				fields=["name", "inspection_template"],
				as_list=True,
			)
		)
	overrides = template_purposes()
	return {
		r.name: purpose_of(
			categories.get(r.get("asset_maintenance")), templates.get(r.get("task")), overrides
		)
		for r in rows
	}


def logs(filters: dict, purpose: str | None = None, fields: list | None = None) -> list:
	"""Asset Maintenance Log rows matching `filters`, limited to one purpose when given."""
	base = ["name", "asset_maintenance", "task"]
	rows = frappe.get_all(LOG, filters=filters, fields=list(dict.fromkeys(base + (fields or []))))
	if purpose is None:
		return rows
	purposes = classify_logs(rows)
	return [r for r in rows if purposes.get(r.name) == purpose]


def safety_override_assets() -> set[str]:
	"""Assets that count as safety only because a Safety-purpose template is used on them."""
	overrides = [t for t, p in template_purposes().items() if p == SAFETY]
	if not overrides:
		return set()
	assets = set()
	if frappe.db.has_column("Asset Maintenance Task", "inspection_template"):
		parents = frappe.get_all(
			"Asset Maintenance Task", filters={"inspection_template": ["in", overrides]}, pluck="parent"
		)
		if parents:
			assets |= set(
				frappe.get_all("Asset Maintenance", filters={"name": ["in", parents]}, pluck="asset_name")
			)
	if frappe.db.table_exists("Asset Inspection"):
		assets |= set(
			frappe.get_all(
				"Asset Inspection",
				filters={"template": ["in", overrides], "docstatus": ["<", 2]},
				pluck="asset",
				distinct=True,
			)
		)
	return {a for a in assets if a}


def asset_purposes(assets: list) -> dict[str, str]:
	"""{asset: purpose} for Asset rows carrying name and asset_category."""
	cat = safety_category()
	extra = safety_override_assets()
	return {a.name: SAFETY if a.asset_category == cat or a.name in extra else MAINTENANCE for a in assets}


def assets(filters: dict, purpose: str | None = None, fields: list | None = None) -> list:
	rows = frappe.get_all(
		"Asset", filters=filters, fields=list(dict.fromkeys(["name", "asset_category"] + (fields or [])))
	)
	if purpose is None:
		return rows
	p = asset_purposes(rows)
	return [r for r in rows if p.get(r.name) == purpose]
