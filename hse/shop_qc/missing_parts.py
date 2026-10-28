# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Missing parts on a build: one list per QC Unit, shared by every QC check on the unit.

The QC Unit's Missing Parts table is the record. Each draft inspection shows a copy (rows keep
the unit row's name in ``part_id``). Saving an inspection pushes new parts and the lines that
were changed in it back to the unit, then refreshes the copy. Parts not yet found are carried
on one open Nonconformance Report per unit, which can only be resolved once every part is Found.
Stages ticked "All Parts Present" (the test stages) cannot be completed while a part is out.
"""

import frappe
from frappe import _
from frappe.utils import cstr, escape_html, flt, format_datetime, now_datetime

from hse.quality_metrics.rework import REWORK, description_values

TABLE = "missing_parts"
CHILD = "QC Missing Part"
OPEN = "Open"
# Fields a check can change on a line; stamps follow from them.
EDIT_FIELDS = ("item_description", "part_number", "qty", "reason", "remarks", "found", "found_on", "found_by")
COPY_FIELDS = (
	*EDIT_FIELDS,
	"found_by_name",
	"found_inspection",
	"reported_stage",
	"reported_inspection",
	"reported_on",
	"reported_by",
	"non_conformance",
)


def _same(field, a, b) -> bool:
	if field in ("qty", "found"):
		return flt(a) == flt(b)
	return cstr(a) == cstr(b)


def current_employee(fallback: str | None = None) -> str | None:
	return (
		frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")
		or fallback
	)


def stamp_rows(rows, before_rows: dict, checker: str | None, inspection=None, stage=None) -> None:
	"""Reported and Found stamps. Found On / Found By typed in the same save are kept."""
	for row in rows:
		if not row.reported_on:
			row.reported_on = now_datetime()
			row.reported_by = row.reported_by or checker
			row.reported_stage = row.reported_stage or stage
			row.reported_inspection = row.reported_inspection or inspection
		old = before_rows.get(row.name)
		if not row.found:
			row.found_on = row.found_by = row.found_by_name = row.found_inspection = None
			continue
		if not (old and old.found):  # newly found
			if not (old and row.found_on and not _same("found_on", row.found_on, old.found_on)):
				row.found_on = now_datetime()
			if not (old and row.found_by and not _same("found_by", row.found_by, old.found_by)):
				row.found_by = checker or row.found_by
			row.found_inspection = inspection
		row.found_on = row.found_on or now_datetime()
		row.found_by = row.found_by or checker
		row.found_by_name = (
			frappe.db.get_value("Employee", row.found_by, "employee_name") if row.found_by else None
		)


def unit_rows(qc_unit: str) -> list:
	return frappe.get_all(
		CHILD,
		filters={"parenttype": "QC Unit", "parent": qc_unit, "parentfield": TABLE},
		fields=["name", "idx", "modified", *COPY_FIELDS],
		order_by="idx asc",
	)


def copy_row(r) -> dict:
	row = {f: r.get(f) for f in COPY_FIELDS}
	row["part_id"] = r.name
	row["part_version"] = cstr(r.modified)
	return row


# ---------------------------------------------------------------- QC Unit
def validate_unit(unit) -> None:
	before = unit.get_doc_before_save()
	old = {r.name: r for r in before.get(TABLE)} if before else {}
	stamp_rows(unit.get(TABLE), old, current_employee())


def on_update_unit(unit) -> None:
	sync_ncr(unit.name)
	refresh_drafts(unit.name)
	# Raising the NCR puts the unit on QC Hold, which moves its modified; keep the open form current.
	unit.modified = frappe.db.get_value("QC Unit", unit.name, "modified")


def refresh_drafts(qc_unit: str, skip: str | None = None) -> None:
	"""Every draft check on the unit shows the unit's current list."""
	rows = unit_rows(qc_unit)
	drafts = frappe.get_all("QC Inspection", filters={"qc_unit": qc_unit, "docstatus": 0}, pluck="name")
	for name in drafts:
		if name == skip:
			continue
		frappe.db.delete(CHILD, {"parenttype": "QC Inspection", "parent": name, "parentfield": TABLE})
		for idx, r in enumerate(rows, 1):
			frappe.get_doc(
				{
					"doctype": CHILD,
					"parenttype": "QC Inspection",
					"parent": name,
					"parentfield": TABLE,
					"idx": idx,
					**copy_row(r),
				}
			).db_insert()


# ---------------------------------------------------------------- QC Inspection
def load_into_inspection(insp) -> None:
	if insp.docstatus == 2 or not insp.qc_unit:
		return
	insp.set(TABLE, [copy_row(r) for r in unit_rows(insp.qc_unit)])


def sync_from_inspection(insp) -> None:
	"""Push new parts and the lines changed in this check to the unit, then refresh the copy.

	A line whose copy is older than the unit's (another check changed it meanwhile) only
	passes on a newly ticked Found, so an outdated copy never un-finds a part."""
	# validate runs on save and on submit (docstatus 1), never on cancel or update after submit
	if insp.docstatus == 2 or not insp.qc_unit or not frappe.db.exists("QC Unit", insp.qc_unit):
		return
	current = {r.name: r for r in unit_rows(insp.qc_unit)}
	checker = current_employee(insp.inspected_by)
	changed = False
	next_idx = max([r.idx for r in current.values()] or [0]) + 1
	for row in insp.get(TABLE):
		if not cstr(row.item_description).strip():
			continue
		if not row.part_id:
			new = frappe.get_doc(
				{
					"doctype": CHILD,
					"parenttype": "QC Unit",
					"parent": insp.qc_unit,
					"parentfield": TABLE,
					"idx": next_idx,
					**{f: row.get(f) for f in EDIT_FIELDS},
				}
			)
			stamp_rows([new], {}, checker, inspection=insp.name, stage=insp.stage)
			new.modified = now_datetime()
			new.db_insert()
			next_idx += 1
			changed = True
			continue
		unit_row = current.get(row.part_id)
		if not unit_row:
			continue  # removed on the unit since this copy was made
		stale = cstr(row.part_version) != cstr(unit_row.modified)
		edits = {
			f: row.get(f)
			for f in EDIT_FIELDS
			if not _same(f, row.get(f), unit_row.get(f)) and (not stale or (f == "found" and row.found))
		}
		if not edits:
			continue
		line = frappe.get_doc(CHILD, row.part_id)
		was = frappe._dict({f: line.get(f) for f in COPY_FIELDS})
		line.update(edits)
		stamp_rows([line], {line.name: was}, checker, inspection=insp.name, stage=insp.stage)
		line.modified = now_datetime()
		line.db_update()
		changed = True
	if changed:
		# Bump the unit's modified so an older open copy of the unit form cannot overwrite the list.
		frappe.db.set_value("QC Unit", insp.qc_unit, "modified_by", frappe.session.user)
		sync_ncr(insp.qc_unit, procedure=insp.quality_procedure)
		refresh_drafts(insp.qc_unit, skip=insp.name)
	load_into_inspection(insp)


def outstanding(qc_unit: str) -> list[dict]:
	return frappe.get_all(
		CHILD,
		filters={"parenttype": "QC Unit", "parent": qc_unit, "parentfield": TABLE, "found": 0},
		fields=["item_description", "part_number", "qty", "reason", "non_conformance"],
		order_by="idx asc",
	)


def check_all_parts_present(insp) -> None:
	"""Stages ticked All Parts Present (testing) cannot be completed with parts outstanding."""
	if not (insp.stage and frappe.get_cached_value("QC Stage", insp.stage, "requires_all_parts")):
		return
	missing = outstanding(insp.qc_unit)
	if missing:
		frappe.throw(
			_("{0} cannot be completed while {1} has missing parts outstanding: {2}").format(
				frappe.bold(insp.stage),
				insp.qc_unit,
				", ".join(_part_label(p) for p in missing),
			),
			title=_("Missing Parts Outstanding"),
		)


def _part_label(p) -> str:
	label = cstr(p.item_description)
	if p.part_number:
		label += f" ({p.part_number})"
	return escape_html(label)


# ---------------------------------------------------------------- Nonconformance Report
def _procedure(qc_unit: str, procedure: str | None) -> str | None:
	return (
		procedure
		or frappe.db.get_value(
			"QC Inspection",
			{"qc_unit": qc_unit, "quality_procedure": ("is", "set")},
			"quality_procedure",
			order_by="creation asc",
		)
		or frappe.db.get_value("Quality Procedure", {}, "name", order_by="creation asc")
	)


def sync_ncr(qc_unit: str, procedure: str | None = None) -> None:
	"""Carry unfound parts on one open NCR per unit and keep its parts list current."""
	rows = frappe.get_all(
		CHILD,
		filters={"parenttype": "QC Unit", "parent": qc_unit, "parentfield": TABLE},
		fields=["name", "idx", *COPY_FIELDS],
		order_by="idx asc",
	)
	status = {
		n: frappe.db.get_value("Nonconformance Report", n, "status")
		for n in {r.non_conformance for r in rows if r.non_conformance}
	}
	need = [r for r in rows if not r.found and status.get(r.non_conformance) != OPEN]
	if need:
		open_ncr = next((n for n, s in status.items() if s == OPEN), None)
		if not open_ncr:
			open_ncr = create_ncr(qc_unit, need, _procedure(qc_unit, procedure))
			status[open_ncr] = OPEN
		for r in need:
			frappe.db.set_value(CHILD, r.name, "non_conformance", open_ncr, update_modified=False)
			r.non_conformance = open_ncr
	for ncr in [n for n, s in status.items() if s == OPEN]:
		parts = [r for r in rows if r.non_conformance == ncr]
		html = parts_table(qc_unit, parts)
		if cstr(frappe.db.get_value("Nonconformance Report", ncr, "details")) != html:
			frappe.db.set_value("Nonconformance Report", ncr, description_values(ncr, html))
			if parts and all(r.found for r in parts):
				frappe.get_doc("Nonconformance Report", ncr).add_comment(
					"Info", _("All missing parts are found. This record can now be resolved.")
				)
				frappe.msgprint(
					_("All missing parts are found; {0} can now be resolved.").format(
						frappe.get_desk_link("Nonconformance Report", ncr)
					),
					indicator="green",
					alert=True,
				)


def create_ncr(qc_unit: str, parts, procedure: str | None) -> str:
	unit = frappe.db.get_value("QC Unit", qc_unit, ["shop"], as_dict=True) or frappe._dict()
	if not procedure:
		frappe.throw(_("Set a Quality Procedure on the inspection template so the Rework can be raised."))
	nc = frappe.get_doc(
		{
			"doctype": "Nonconformance Report",
			# QM-104 Rev. 3: a missing part is reworked to drawing once found; it is not an NCR.
			# If it turns out to meet the NCR criteria, Escalate to NCR moves the parts across.
			"record_type": REWORK,
			"subject": f"{unit.shop or 'QC'} missing parts - {qc_unit}",
			"procedure": procedure,
			"status": OPEN,
			"source": "In-Process Inspection",
			"severity": "Medium",
			"details": parts_table(qc_unit, parts),
			"rw_requirement": parts_table(qc_unit, parts),
			"qc_unit": qc_unit,
			"interim_control": _("Unit on QC Hold; testing and release wait until every part is found."),
		}
	)
	nc.flags.ignore_permissions = True
	nc.insert()
	frappe.msgprint(
		_("Rework {0} raised for missing parts on {1}.").format(
			frappe.get_desk_link("Nonconformance Report", nc.name), qc_unit
		),
		indicator="orange",
		alert=True,
	)
	return nc.name


def parts_table(qc_unit: str, parts) -> str:
	head = "".join(
		f"<th>{_(h)}</th>"
		for h in ("Part Description", "Part #", "Qty.", "Reason", "Reported", "Found", "Remarks")
	)
	body = "".join(
		"<tr>"
		+ "".join(
			f"<td>{v}</td>"
			for v in (
				escape_html(cstr(r.item_description)),
				escape_html(cstr(r.part_number)),
				cstr(flt(r.qty) or ""),
				escape_html(_(r.reason) if r.reason else ""),
				escape_html(
					" ".join(
						x
						for x in (
							cstr(r.reported_stage),
							format_datetime(r.reported_on, "MM-dd-yyyy") if r.reported_on else "",
						)
						if x
					)
				),
				escape_html(
					_("Yes") + (" " + format_datetime(r.found_on, "MM-dd-yyyy") if r.found_on else "")
					if r.found
					else _("No")
				),
				escape_html(cstr(r.remarks)),
			)
		)
		+ "</tr>"
		for r in parts
	)
	return (
		f"<p>{_('QC Unit')}: <b>{escape_html(qc_unit)}</b> - {_('Missing parts')}</p>"
		f"<table class='table table-bordered'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
	)


def validate_ncr_closure(doc, method=None) -> None:
	"""An NCR or Rework carrying missing parts can be resolved only once every part is Found."""
	if doc.status != "Resolved" or doc.is_new():
		return
	missing = frappe.get_all(
		CHILD,
		filters={"parenttype": "QC Unit", "non_conformance": doc.name, "found": 0},
		fields=["item_description", "part_number"],
		order_by="idx asc",
	)
	if missing:
		frappe.throw(
			_("Cannot resolve this record until every missing part is marked Found: {0}").format(
				", ".join(_part_label(p) for p in missing)
			),
			title=_("Resolution Blocked"),
		)
