# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Confined Space Permit: the entry permit of 29 CFR 1910.146(f).

The entry supervisor issues the permit by submitting it, once the entrants and attendants are
named, the hazards and the measures that control them are recorded, rescue and communication
are arranged and a pre-entry atmospheric test is within the acceptable entry conditions. Tests
and personnel can be added while the permit is issued; a reading outside the limits is a
prohibited condition."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, flt, get_datetime, now_datetime

from hse.hse.permits import (
	has_text,
	same_person,
	user_has_any_role,
	warn_unqualified,
	window_errors,
	workers_with_role,
)

DRAFT, ISSUED, CANCELLED = "Draft", "Issued", "Cancelled"
ACCEPTABLE, NOT_ACCEPTABLE = "Acceptable", "Not Acceptable"
ENTRANT, ATTENDANT = "Entrant", "Attendant"
HAZARD_CHECKS = (
	"hz_oxygen",
	"hz_flammable",
	"hz_toxic",
	"hz_engulfment",
	"hz_entrapment",
	"hz_mechanical",
	"hz_electrical",
	"hz_pressure",
	"hz_thermal",
	"hz_noise",
)
ISOLATION_CHECKS = (
	"iso_lockout",
	"iso_blanked",
	"iso_purged",
	"iso_inerted",
	"iso_ventilated",
	"iso_barricade",
)
# May issue a permit naming someone else as entry supervisor.
OVERRIDE_ROLES = ("Safety Manager", "System Manager")


def judge_reading(test, limits) -> str:
	"""Acceptable / Not Acceptable against the permit's limits; "" until oxygen is entered.
	Frappe saves an empty Float as 0, so an oxygen reading of 0 counts as not taken; blank LEL
	and toxic readings count as 0."""
	o2 = flt(test.oxygen_pct)
	if not o2:
		return ""
	bad = (
		o2 < flt(limits.oxygen_min)
		or o2 > flt(limits.oxygen_max)
		or flt(test.lel_pct) > flt(limits.lel_max)
		or (flt(limits.h2s_max) and flt(test.h2s_ppm) > flt(limits.h2s_max))
		or (flt(limits.co_max) and flt(test.co_ppm) > flt(limits.co_max))
	)
	return NOT_ACCEPTABLE if bad else ACCEPTABLE


def latest_test(tests):
	dated = [t for t in tests if t.test_time]
	return max(dated, key=lambda t: get_datetime(t.test_time)) if dated else None


def issue_errors(doc) -> list[str]:
	errors = window_errors(doc, "permit_start", "permit_end", issuing=True)
	entrants = workers_with_role(doc.workers, ENTRANT)
	attendants = workers_with_role(doc.workers, ATTENDANT)
	if not entrants:
		errors.append(_("Name at least one authorized entrant (Role: Entrant)."))
	if not attendants:
		errors.append(_("Name at least one attendant (Role: Attendant)."))
	both = [e.worker_name for e in entrants if any(same_person(e, a) for a in attendants)]
	if both:
		errors.append(
			_("{0}: an attendant stays outside the space and cannot also be an entrant.").format(
				", ".join(both)
			)
		)
	if not any(doc.get(f) for f in HAZARD_CHECKS) and not has_text(doc.hz_other):
		errors.append(_("Record the hazards of the permit space."))
	if not any(doc.get(f) for f in ISOLATION_CHECKS) and not has_text(doc.iso_other):
		errors.append(_("Record how the space is isolated and its hazards controlled."))
	if not doc.rescue_service or not has_text(doc.summon_rescue):
		errors.append(_("Record the rescue arrangement and how to summon rescue."))
	if not doc.communication_method:
		errors.append(_("Select how entrants and attendants communicate."))
	pre_entry = [t for t in doc.atmospheric_tests if t.test_type == "Pre-Entry" and t.result]
	if not pre_entry:
		errors.append(_("Record a pre-entry atmospheric test with oxygen, LEL and toxic gas readings."))
	else:
		last = latest_test(doc.atmospheric_tests)
		if last and last.result == NOT_ACCEPTABLE:
			errors.append(
				_("The latest atmospheric test (row {0}) is outside the acceptable entry conditions.").format(
					last.idx
				)
			)
	return errors


class ConfinedSpacePermit(Document):
	def validate(self):
		if self.docstatus == 0:
			self.status = DRAFT
		self.check_limits()
		self.judge_tests()
		if errors := window_errors(self, "permit_start", "permit_end"):
			frappe.throw("<br>".join(errors), title=_("Confined Space Permit"))

	def before_submit(self):
		if errors := issue_errors(self):
			frappe.throw("<br>".join(errors), title=_("Cannot Issue Permit"))
		self.check_issuer()
		self.status = ISSUED
		self.issued_by = frappe.session.user
		self.issued_on = now_datetime()

	def on_submit(self):
		warn_unqualified(self, "Confined Space", (ENTRANT, ATTENDANT), _("confined space entry"))

	def before_update_after_submit(self):
		self.judge_tests()
		if self.status == ISSUED:
			last = latest_test(self.atmospheric_tests)
			if last and last.result == NOT_ACCEPTABLE:
				frappe.msgprint(
					_(
						"Test row {0} is outside the acceptable entry conditions. Entrants must leave the "
						"space now. Close the permit as Prohibited Condition."
					).format(last.idx),
					title=_("Prohibited Condition"),
					indicator="red",
				)

	def on_cancel(self):
		self.db_set("status", CANCELLED)

	def check_limits(self):
		if flt(self.oxygen_min) >= flt(self.oxygen_max):
			frappe.throw(_("O₂ Minimum must be below O₂ Maximum."), title=_("Acceptable Entry Conditions"))

	def judge_tests(self):
		for t in self.atmospheric_tests:
			t.result = judge_reading(t, self)

	def check_issuer(self):
		"""1910.146(e)(2): the entry supervisor signs the permit."""
		supervisor_user = frappe.db.get_value("Employee", self.entry_supervisor, "user_id")
		if (
			supervisor_user
			and supervisor_user != frappe.session.user
			and not user_has_any_role(OVERRIDE_ROLES)
		):
			frappe.throw(
				_("Only the entry supervisor ({0}) or a Safety Manager can issue this permit.").format(
					self.entry_supervisor_name or self.entry_supervisor
				),
				title=_("Cannot Issue Permit"),
			)


@frappe.whitelist()
def make_from_jha(source_name: str):
	"""A draft permit from an approved Job Hazard Analysis."""
	jha = frappe.get_doc("Job Hazard Analysis", source_name)
	jha.check_permission("read")
	doc = frappe.new_doc("Confined Space Permit")
	doc.update(
		{
			"company": jha.company,
			"location": jha.location,
			"asset": jha.asset,
			"job_hazard_analysis": jha.name,
			"purpose": jha.job_title,
			"iso_lockout": jha.req_loto,
			"hot_work_permit": jha.req_hot_work,
			"eq_ppe": cstr(jha.ppe_other),
		}
	)
	return doc
