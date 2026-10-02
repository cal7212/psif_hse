# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""OSHA Form 300 - Log of Work-Related Injuries and Illnesses."""

import frappe
from frappe import _
from frappe.utils import cint, getdate, nowdate

from hse.hse.osha_recordkeeping import ILLNESS_TYPES, get_cases, summarize


def execute(filters=None):
	filters = frappe._dict(filters or {})
	year = cint(filters.year) or getdate(nowdate()).year
	cases = get_cases(year, include_drafts=cint(filters.include_drafts))
	totals = summarize(cases)

	message = None
	if any(c.draft for c in cases):
		message = _("Includes draft reports. Submit them before posting or certifying the 300A.")
	if totals.cases_missing_type:
		warn = _("{0} case(s) have no OSHA Injury/Illness Classification (column M).").format(
			totals.cases_missing_type
		)
		message = f"{message} {warn}" if message else warn

	return get_columns(), cases, message, None, get_summary(totals)


def get_columns():
	return [
		{"label": _("(A) Case No."), "fieldname": "case_no", "fieldtype": "Link", "options": "Injury_Illness Report", "width": 140},
		{"label": _("(B) Employee"), "fieldname": "employee", "fieldtype": "Data", "width": 150},
		{"label": _("(C) Job Title"), "fieldname": "job_title", "fieldtype": "Data", "width": 120},
		{"label": _("(D) Date"), "fieldname": "incident_date", "fieldtype": "Date", "width": 95},
		{"label": _("(E) Where"), "fieldname": "location", "fieldtype": "Data", "width": 120},
		{"label": _("(F) Description"), "fieldname": "description", "fieldtype": "Data", "width": 240},
		{"label": _("(G-J) Outcome"), "fieldname": "outcome_label", "fieldtype": "Data", "width": 170},
		{"label": _("(K) Days Away"), "fieldname": "days_away", "fieldtype": "Int", "width": 90},
		{"label": _("(L) Days Restricted"), "fieldname": "days_restricted", "fieldtype": "Int", "width": 110},
		{"label": _("(M) Type"), "fieldname": "illness_type", "fieldtype": "Data", "width": 150},
	]


def get_summary(t):
	cards = [
		(_("Deaths (G)"), t.total_deaths),
		(_("Days Away Cases (H)"), t.total_days_away_cases),
		(_("Transfer/Restriction Cases (I)"), t.total_transfer_cases),
		(_("Other Recordable (J)"), t.total_other_cases),
		(_("Days Away (K)"), t.total_days_away),
		(_("Days Restricted (L)"), t.total_transfer_days),
	]
	cards += [(_(label), t[f"total_{key}"]) for label, key in ILLNESS_TYPES]
	return [{"label": label, "value": value, "datatype": "Int", "indicator": "blue"} for label, value in cards]
