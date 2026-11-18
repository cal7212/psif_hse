# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Smartsheet -> QC Unit date sync.

Reads one Smartsheet sheet, finds each row by its work order and copies the row's dates onto
every QC Unit of that work order (each unit of a multi-unit order, and its hose build).

Put in hse/shop_qc/smartsheet_sync.py. Configure with:
	bench --site <site> set-config smartsheet_api_token "<token>"
	bench --site <site> set-config smartsheet_sheet_id "<sheet id>"
	# only for an EU/Gov account:
	bench --site <site> set-config smartsheet_api_url "https://api.smartsheet.eu/2.0"

Scheduled from hooks.py; run by hand with:
	bench --site <site> execute hse.shop_qc.smartsheet_sync.sync_dates --kwargs "{'dry_run': True}"
"""

import frappe
import requests
from frappe import _
from frappe.utils import getdate, sbool

from hse.shop_qc.doctype.qc_unit.qc_unit import normalise_wo
from hse.shop_qc.utils import LOCKED_STATUSES

DEFAULT_API_URL = "https://api.smartsheet.com/2.0"

# Smartsheet column titles (matched case-insensitively).
WO_COLUMN = "Work Order"
DATE_COLUMNS = {
	"Promise Date": "promised_date",
	"Finish Date": "target_date",
}
# Like the TrulinX sync, a blank Smartsheet cell does not wipe a date already in Frappe.
CLEAR_WHEN_BLANK = False


def scheduled() -> None:
	"""Scheduler entry point: does nothing until the site is configured."""
	if not (frappe.conf.get("smartsheet_api_token") and frappe.conf.get("smartsheet_sheet_id")):
		return
	try:
		sync_dates()
	except Exception:
		frappe.log_error(title="Smartsheet date sync failed")


@frappe.whitelist(methods=["POST"])
def sync_now(dry_run: bool = False) -> dict:
	"""Manual run, e.g. from a button on the QC Unit list."""
	frappe.only_for("System Manager")
	return sync_dates(dry_run=sbool(dry_run))


def sync_dates(dry_run: bool = False) -> dict:
	sheet = _get_sheet()
	cols = {cstr_lower(c.get("title")): c["id"] for c in sheet.get("columns", [])}
	missing = [t for t in (WO_COLUMN, *DATE_COLUMNS) if t.lower() not in cols]
	if missing:
		frappe.throw(_("Smartsheet column(s) not found: {0}").format(", ".join(missing)))

	wo_col = cols[WO_COLUMN.lower()]
	date_cols = {cols[title.lower()]: field for title, field in DATE_COLUMNS.items()}

	# Work order -> {field: date}. A work order on more than one row is skipped, not guessed.
	by_wo: dict[str, dict] = {}
	duplicates: set[str] = set()
	for row in sheet.get("rows", []):
		cells = {c.get("columnId"): c.get("value") for c in row.get("cells", [])}
		wo = _wo(cells.get(wo_col))
		if not wo:
			continue
		if wo in by_wo:
			duplicates.add(wo)
			continue
		by_wo[wo] = {field: _date(cells.get(col_id)) for col_id, field in date_cols.items()}
	for wo in duplicates:
		by_wo.pop(wo, None)

	# One query for every open unit; matched in Python rather than a huge IN (...) filter.
	units = frappe.get_all(
		"QC Unit",
		filters={"trulinx_work_order": ("is", "set"), "status": ("not in", LOCKED_STATUSES)},
		fields=["name", "trulinx_work_order", *DATE_COLUMNS.values()],
	)

	result = {"updated": [], "unchanged": 0, "not_in_frappe": [], "duplicates": sorted(duplicates)}
	matched = set()
	for u in units:
		dates = by_wo.get(normalise_wo(u.trulinx_work_order))
		if dates is None:
			continue
		matched.add(normalise_wo(u.trulinx_work_order))
		changes = {
			field: value
			for field, value in dates.items()
			if (value or CLEAR_WHEN_BLANK) and (u.get(field) or None) != value
		}
		if not changes:
			result["unchanged"] += 1
			continue
		result["updated"].append(u.name)
		if not dry_run:
			_apply(u, changes)

	result["not_in_frappe"] = sorted(set(by_wo) - matched)
	return result


def _apply(unit, changes: dict) -> None:
	# set_value, not doc.save(): a date change should not run the whole QC Unit validate
	# (stage rebuilds, status checks), and an unrelated validation error must not block it.
	# update_modified=False so a form someone has open can still be saved.
	frappe.db.set_value("QC Unit", unit.name, changes, update_modified=False)
	meta = frappe.get_meta("QC Unit")
	lines = [
		_("{0}: {1} → {2}").format(
			_(meta.get_label(field)), unit.get(field) or _("(blank)"), value or _("(blank)")
		)
		for field, value in changes.items()
	]
	frappe.get_doc(
		{
			"doctype": "Comment",
			"comment_type": "Info",
			"reference_doctype": "QC Unit",
			"reference_name": unit.name,
			"content": _("Updated from Smartsheet") + "<br>" + "<br>".join(lines),
		}
	).insert(ignore_permissions=True)


def _get_sheet() -> dict:
	base = (frappe.conf.get("smartsheet_api_url") or DEFAULT_API_URL).rstrip("/")
	sheet_id = frappe.conf.get("smartsheet_sheet_id")
	token = frappe.conf.get("smartsheet_api_token")
	if not (sheet_id and token):
		frappe.throw(_("Set smartsheet_api_token and smartsheet_sheet_id in site_config.json."))
	r = requests.get(
		f"{base}/sheets/{sheet_id}",
		headers={"Authorization": f"Bearer {token}"},
		timeout=60,
	)
	r.raise_for_status()
	return r.json()


def _wo(value) -> str | None:
	# A work order typed into a number column comes back as 12345.0.
	if isinstance(value, float) and value.is_integer():
		value = int(value)
	return normalise_wo(value) or None


def _date(value):
	"""Smartsheet date columns return 'YYYY-MM-DD'; date-time columns add a time part."""
	if value in (None, ""):
		return None
	try:
		return getdate(str(value)[:10] if "T" in str(value) else value)
	except Exception:
		return None


def cstr_lower(value) -> str:
	return (value or "").strip().lower()
