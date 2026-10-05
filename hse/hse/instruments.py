# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Test equipment rules shared by QC Inspection and Asset Inspection.

An inspection lists its instruments in an `instruments` table (Inspection Instrument).
Reading rows carry an `instrument` link. Before submit every listed instrument must be
Active and, if it needs calibration, in calibration on the inspection date. The calibration
due date is copied onto the row so the record shows the status at the time of use.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

PRESSURE_TYPES = ("Pressure Gauge", "Pressure Transducer")
CRIMP_TYPES = ("Caliper / Micrometer",)
AMPS_TYPES = ("Clamp Meter", "Multimeter", "Power Quality Analyzer")


def needs_instrument(row) -> bool:
	"""A numeric reading judged against a limit must name its instrument. Record-only values
	(odometer, hour meter) have no limit and do not."""
	return bool(row.numeric and row.result != "N/A" and (flt(row.min_value) or flt(row.max_value)))


def listed_instruments(doc) -> list[str]:
	names = [r.instrument for r in doc.get("instruments") or [] if r.instrument]
	dupes = sorted({n for n in names if names.count(n) > 1})
	if dupes:
		frappe.throw(_("Instrument {0} is listed more than once.").format(", ".join(dupes)))
	return names


def instrument_types(names: list[str]) -> dict:
	if not names:
		return {}
	return dict(
		frappe.get_all(
			"Measuring Instrument",
			filters={"name": ("in", names)},
			fields=["name", "instrument_type"],
			as_list=True,
		)
	)


def pick(names: list[str], types: dict, allowed: tuple | None = None) -> str | None:
	"""The instrument to default to: the only one listed, or the only one of an allowed type."""
	if len(names) == 1 and (not allowed or types.get(names[0]) in allowed):
		return names[0]
	if allowed:
		matching = [n for n in names if types.get(n) in allowed]
		if len(matching) == 1:
			return matching[0]
	return None


def add_used_instruments(doc, used: list[str]):
	"""Every instrument a reading names is also listed in the Test Equipment table."""
	listed = [r.instrument for r in doc.get("instruments") or []]
	for name in dict.fromkeys(u for u in used if u):
		if name not in listed:
			doc.append("instruments", {"instrument": name})
			listed.append(name)


def check_listed_instruments(doc, on_date) -> list[str]:
	"""Errors for listed instruments that are not usable on `on_date`; snapshots their data."""
	errors = []
	on = getdate(on_date)
	for row in doc.get("instruments") or []:
		inst = frappe.db.get_value(
			"Measuring Instrument",
			row.instrument,
			[
				"status",
				"calibration_required",
				"calibration_due",
				"instrument_type",
				"serial_no",
				"measuring_range",
			],
			as_dict=True,
		)
		if not inst:
			errors.append(_("Instrument {0} does not exist.").format(frappe.bold(row.instrument)))
			continue
		row.update(
			{
				"calibration_due": inst.calibration_due,
				"instrument_type": inst.instrument_type,
				"serial_no": inst.serial_no,
				"measuring_range": inst.measuring_range,
			}
		)
		if inst.status != "Active":
			errors.append(_("Instrument {0} is {1}.").format(frappe.bold(row.instrument), _(inst.status)))
		elif not cint(inst.calibration_required):
			continue
		elif not inst.calibration_due:
			errors.append(
				_(
					"Instrument {0} has no calibration due date. Update its Measuring Instrument record."
				).format(frappe.bold(row.instrument))
			)
		elif getdate(inst.calibration_due) < on:
			errors.append(
				_("Instrument {0} was out of calibration on the inspection date (due {1}).").format(
					frappe.bold(row.instrument), frappe.format(inst.calibration_due, "Date")
				)
			)
	return errors
