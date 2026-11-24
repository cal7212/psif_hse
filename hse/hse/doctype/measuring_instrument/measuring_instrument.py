# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, cint, cstr, getdate, nowdate

OVERDUE = "Calibration Overdue"
OUT_OF_TOLERANCE = "Out of Tolerance"
# Inspections whose Test Equipment table names the instrument, and their date field.
USING_DOCTYPES = (("QC Inspection", "inspection_date"), ("Asset Inspection", "inspection_date"))


class MeasuringInstrument(Document):
	def before_naming(self):
		self.instrument_id = cstr(self.instrument_id).strip().upper()

	def validate(self):
		self.instrument_id = cstr(self.instrument_id).strip().upper()
		if not cint(self.calibration_required):
			return
		self.apply_calibration_history()
		if self.last_calibrated and cint(self.calibration_interval_months) > 0:
			self.calibration_due = add_months(self.last_calibrated, cint(self.calibration_interval_months))
		if (
			self.last_calibrated
			and self.calibration_due
			and getdate(self.calibration_due) < getdate(self.last_calibrated)
		):
			frappe.throw(_("Calibration Due cannot be before Last Calibrated."))
		if self.status == OVERDUE and self.calibration_due and getdate(self.calibration_due) >= getdate():
			self.status = "Active"

	def apply_calibration_history(self):
		"""QM-400 7.1.5: each calibration is kept as a row; the latest one sets the instrument's
		current calibration fields."""
		rows = sorted(self.calibrations or [], key=lambda r: getdate(r.calibration_date))
		if not rows:
			return
		for idx, row in enumerate(rows, start=1):
			row.idx = idx
			if getdate(row.calibration_date) > getdate(nowdate()):
				frappe.throw(_("Calibration History row {0}: the date cannot be in the future.").format(idx))
			if cint(self.calibration_interval_months) > 0:
				row.next_due = add_months(row.calibration_date, cint(self.calibration_interval_months))
		self.calibrations = rows
		latest = rows[-1]
		self.last_calibrated = latest.calibration_date
		self.calibrated_by = latest.calibrated_by or self.calibrated_by
		self.calibration_certificate = latest.certificate or self.calibration_certificate
		self.calibration_certificate_location = (
			cstr(latest.certificate_location).strip() or self.calibration_certificate_location
		)
		for row in rows:
			row.certificate_location = cstr(row.certificate_location).strip() or None
		if latest.as_left == "Failed - Removed from Service" and self.status in ("Active", OVERDUE):
			self.status = "Out for Calibration"
			frappe.msgprint(
				_("The last calibration failed; the instrument is set to Out for Calibration."),
				indicator="orange",
				alert=True,
			)

	def on_update(self):
		for row in self.calibrations or []:
			if row.as_found == OUT_OF_TOLERANCE and not row.impact_ncr:
				ncr = raise_impact_ncr(self, row)
				row.db_set("impact_ncr", ncr, update_modified=False)


def previous_calibration_date(doc, row):
	earlier = [
		getdate(r.calibration_date)
		for r in doc.calibrations
		if r.name != row.name and getdate(r.calibration_date) < getdate(row.calibration_date)
	]
	return max(earlier) if earlier else None


def inspections_using(instrument: str, since, until) -> list[tuple[str, str, str]]:
	"""Submitted inspections that listed the instrument between two calibrations."""
	found = []
	for doctype, date_field in USING_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		parents = frappe.get_all(
			"Inspection Instrument",
			filters={"parenttype": doctype, "instrument": instrument},
			pluck="parent",
		)
		if not parents:
			continue
		filters = {"name": ("in", list(set(parents))), "docstatus": 1}
		if since:
			filters[date_field] = (">=", since)
		rows = frappe.get_all(doctype, filters=filters, fields=["name", date_field])
		for r in rows:
			if getdate(r.get(date_field)) <= getdate(until):
				found.append((doctype, r.name, str(getdate(r.get(date_field)))))
	return sorted(found, key=lambda x: x[2])


def raise_impact_ncr(doc, row) -> str:
	"""QM-400 7.1.5.2: an instrument found out of tolerance needs an evaluation of the results it
	gave since its last good calibration. The NCR lists them for the reviewer."""
	since = previous_calibration_date(doc, row)
	used = inspections_using(doc.name, since, row.calibration_date)
	lines = "".join(f"<li>{frappe.utils.escape_html(dt)} {name} ({date})</li>" for dt, name, date in used)
	details = _(
		"<p>{0} was found out of tolerance at calibration on {1}. Evaluate whether these results "
		"are still valid, re-test or notify the customer where they are not (QM-400 7.1.5.2).</p>"
	).format(frappe.utils.escape_html(doc.name), row.calibration_date)
	details += f"<ul>{lines}</ul>" if lines else _("<p>No submitted inspections used it in that period.</p>")
	if row.notes:
		details += f"<p>{frappe.utils.escape_html(row.notes)}</p>"
	ncr = frappe.get_doc(
		{
			"doctype": "Nonconformance Report",
			"subject": _("Out-of-tolerance calibration: {0}").format(doc.name)[:140],
			"status": "Open",
			"source": "Calibration",
			"severity": "High" if used else "Medium",
			"details": details,
		}
	)
	ncr.flags.ignore_permissions = True
	ncr.insert()
	frappe.msgprint(
		_("Nonconformance Report {0} opened to evaluate {1} inspection(s) that used this instrument.").format(
			frappe.get_desk_link("Nonconformance Report", ncr.name), len(used)
		),
		indicator="orange",
	)
	return ncr.name


def flag_overdue_calibrations():
	"""Daily: Active instruments past their calibration due date become Calibration Overdue."""
	for name in frappe.get_all(
		"Measuring Instrument",
		filters={"status": "Active", "calibration_required": 1, "calibration_due": ("<", nowdate())},
		pluck="name",
	):
		frappe.db.set_value("Measuring Instrument", name, "status", OVERDUE)
