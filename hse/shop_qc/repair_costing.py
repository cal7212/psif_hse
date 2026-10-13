# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Repair Costing Worksheet math (mirrors the PSIF REPAIR COSTING WORKSHEET).

Percentages are stored as whole numbers (5 means 5 %). The line Multiplier is a
fraction of list price (0.5 means 50 %), entered by the user per line.
"""

from frappe.utils import flt

# Build Shop default -> QC Unit field(s)
SHOP_DEFAULTS = {
	"default_burden_pct": ("parts_burden_pct", "accessories_burden_pct"),
	"default_inbound_freight_pct": ("parts_freight_pct", "accessories_freight_pct"),
	"default_expendables_pct": ("parts_expendables_pct", "accessories_expendables_pct"),
	"default_margin_pct": ("parts_margin_pct", "accessories_margin_pct"),
	"default_labor_cost_rate": ("labor_cost_rate",),
	"default_labor_sell_rate": ("labor_sell_rate",),
}


def calc_line(row) -> None:
	row.cost_each = flt(row.list_price) * flt(row.multiplier)
	row.extended_cost = flt(row.qty) * flt(row.cost_each)


def sell_price(cost: float, margin_pct: float) -> float:
	"""Sell = Cost / (1 - Margin). A margin of 100 % or more has no price."""
	margin = flt(margin_pct) / 100
	if margin >= 1:
		return 0.0
	return flt(cost) / (1 - margin)


def calc_group(doc, prefix: str, rows) -> None:
	total = sum(flt(r.extended_cost) for r in rows)
	doc.set(f"{prefix}_total", total)
	cost = total
	for part in ("burden", "freight", "expendables"):
		amount = total * flt(doc.get(f"{prefix}_{part}_pct")) / 100
		doc.set(f"{prefix}_{part}", amount)
		cost += amount
	doc.set(f"{prefix}_cost_total", cost)
	sell = sell_price(cost, doc.get(f"{prefix}_margin_pct")) if cost else 0.0
	doc.set(f"{prefix}_sell_price", sell)
	doc.set(f"{prefix}_margin", sell - cost if sell else 0.0)


def calc_repair_costing(doc) -> None:
	"""Recalculate every derived costing field on a repair QC Unit (Document or dict-like)."""
	for table in ("repair_parts", "accessory_items"):
		for row in doc.get(table) or []:
			calc_line(row)
	calc_group(doc, "parts", doc.get("repair_parts") or [])
	calc_group(doc, "accessories", doc.get("accessory_items") or [])

	insp, rep, assy, test = (
		flt(doc.get(f))
		for f in ("labor_inspection_hr", "labor_repair_hr", "labor_assembly_hr", "labor_testing_hr")
	)
	hours = insp + rep + assy + test
	doc.labor_total_hr = hours
	doc.labor_inspection_cost_hr = insp
	doc.labor_rep_assy_hr = rep + assy
	doc.labor_testing_cost_hr = test
	doc.labor_cost = hours * flt(doc.get("labor_cost_rate"))
	doc.labor_sell_price = hours * flt(doc.get("labor_sell_rate"))

	doc.repair_price = flt(doc.parts_sell_price) + flt(doc.labor_sell_price)
	doc.repair_accessories_price = doc.repair_price + flt(doc.accessories_sell_price)
	new_unit = flt(doc.get("new_unit_price"))
	new_acc = flt(doc.get("new_unit_accessories_price"))
	doc.repair_pct_of_new = doc.repair_price / new_unit * 100 if new_unit else 0.0
	doc.repair_accessories_pct_of_new = doc.repair_accessories_price / new_acc * 100 if new_acc else 0.0


def load_shop_defaults(doc, shop_values: dict) -> None:
	"""Copy the Repair shop's costing defaults once; later edits on the unit are kept."""
	if doc.get("costing_defaults_loaded"):
		return
	for src, targets in SHOP_DEFAULTS.items():
		value = flt(shop_values.get(src))
		for t in targets:
			if not flt(doc.get(t)) and value:
				doc.set(t, value)
	doc.costing_defaults_loaded = 1
