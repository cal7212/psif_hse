# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, flt


def normalise_fitting(value) -> str:
	return cstr(value).strip().upper().replace(" ", "")


# A chart key such as T2000, TP000, TW4000, 66000N, 1G000, 1100 or 7200-M names a coupling
# series rather than one fitting part number.
SERIES_KEY = re.compile(r"^([A-Z0-9_]+?)0{2,}(-?[A-Z])?$")


def series_prefix(key: str) -> str | None:
	"""'T2000' -> 'T2', '66000N' -> '66', '7200-M' -> '72'. None when the key is a part number."""
	m = SERIES_KEY.match(normalise_fitting(key))
	if not m:
		return None
	prefix = m.group(1).rstrip("0")
	return prefix if len(prefix) >= 2 else None


class HoseCrimpSpec(Document):
	def validate(self):
		from hse.shop_qc.doctype.qc_unit.qc_unit import normalise_dash

		self.dash_size = normalise_dash(self.dash_size)[0]
		self.fitting_part_number = normalise_fitting(self.fitting_part_number)
		if flt(self.crimp_diameter) <= 0:
			frappe.throw(_("Crimp Diameter must be greater than zero."))
		if flt(self.crimp_tolerance) < 0:
			frappe.throw(_("Crimp Tolerance must be positive."))
		self.title = f"{self.hose_type} {self.dash_size} {self.fitting_part_number}"
		dupe = frappe.db.get_value(
			"Hose Crimp Spec",
			{
				"hose_type": self.hose_type,
				"dash_size": self.dash_size,
				"fitting_part_number": self.fitting_part_number,
				"name": ("!=", self.name),
			},
		)
		if dupe:
			frappe.throw(
				_("{0} already has a crimp spec for this hose type, dash size and fitting.").format(dupe),
				frappe.DuplicateEntryError,
			)


def find_crimp_spec(hose_type, dash_size, fitting) -> frappe._dict | None:
	"""Active chart row for this hose type, dash size and fitting.

	An entry for the exact fitting part number wins. Otherwise the fitting is matched to a
	coupling-series entry by part-number prefix (T2040-1212 -> T2000), longest prefix first.
	The returned row carries `matched_series` when it was found by series."""
	from hse.shop_qc.doctype.qc_unit.qc_unit import normalise_dash

	if not (hose_type and dash_size and fitting):
		return None
	part = normalise_fitting(fitting)
	rows = frappe.get_all(
		"Hose Crimp Spec",
		filters={"hose_type": hose_type, "dash_size": normalise_dash(dash_size)[0], "disabled": 0},
		fields=[
			"name",
			"fitting_part_number",
			"crimp_diameter",
			"crimp_tolerance",
			"die_size",
			"source",
			"revision",
		],
	)
	best, best_len = None, 0
	for row in rows:
		key = normalise_fitting(row.fitting_part_number)
		if key == part:
			row.matched_series = None
			return row
		prefix = series_prefix(key)
		if prefix and len(part) > len(prefix) and part.startswith(prefix) and len(prefix) > best_len:
			best, best_len = row, len(prefix)
	if best:
		best.matched_series = normalise_fitting(best.fitting_part_number)
	return best


@frappe.whitelist()
def get_crimp_spec(hose_type: str, dash_size: str, fitting: str) -> dict | None:
	frappe.has_permission("Hose Crimp Spec", "read", throw=True)
	return find_crimp_spec(hose_type, dash_size, fitting)
