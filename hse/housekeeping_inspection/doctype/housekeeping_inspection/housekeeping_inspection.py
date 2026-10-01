# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cstr, escape_html, flt, getdate

from hse.housekeeping_inspection.utils import (
	AS_NEEDED,
	AWAITING_RETURN,
	close_area_todos,
	next_due,
	refresh_area_last_inspection,
	schedule_status_for,
	trip_status,
	update_area_housekeeping_status,
)

PASS, FAIL, NA = "Pass", "Fail", "N/A"
TEMPLATE_ROW_FIELDS = ("category", "check_item", "criteria", "is_critical", "reference")


def summarize(rows, passing_score=0):
	"""Score and grade a checklist.

	rows: iterable of dicts/objects with result, is_critical, corrected_on_spot.
	Score = passed / applicable (Pass + Fail) x 100; N/A items are excluded.
	Items corrected on the spot still count as failed in the score (the
	condition was found), but do not require a Non Conformance.

	Rejected when any failed item was NOT corrected on the spot, or the score
	is below the passing score. Severity for the Non Conformance:
	Critical = open critical failure, Medium = open non-critical failure,
	Low = only the score was below passing.
	"""
	get = lambda r, k: (r.get(k) if isinstance(r, dict) else getattr(r, k, None))
	checked = [r for r in rows if get(r, "result") in (PASS, FAIL)]
	failed = [r for r in checked if get(r, "result") == FAIL]
	corrected = [r for r in failed if get(r, "corrected_on_spot")]
	open_fails = [r for r in failed if not get(r, "corrected_on_spot")]

	score = round(100.0 * (len(checked) - len(failed)) / len(checked), 1) if checked else 100.0
	below = bool(passing_score) and score < flt(passing_score)

	if any(get(r, "is_critical") for r in open_fails):
		severity = "Critical"
	elif open_fails:
		severity = "Medium"
	elif below:
		severity = "Low"
	else:
		severity = None

	return frappe._dict(
		score=score,
		items_checked=len(checked),
		items_failed=len(failed),
		corrected_on_spot_count=len(corrected),
		open_findings=len(open_fails),
		below_passing=below,
		status="Rejected" if severity else "Accepted",
		severity=severity,
	)


class HousekeepingInspection(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hse.housekeeping_inspection.doctype.housekeeping_inspection_item.housekeeping_inspection_item import HousekeepingInspectionItem

		amended_from: DF.Link | None
		area_owner: DF.Link | None
		company: DF.Link | None
		corrected_on_spot_count: DF.Int
		department: DF.Link | None
		housekeeping_area: DF.Link
		inspected_by: DF.Link
		inspection_date: DF.Datetime
		inspection_reason: DF.Literal["Routine", "Pre-Departure", "Post-Return"]
		inspector_name: DF.Data | None
		is_reinspection: DF.Check
		items: DF.Table[HousekeepingInspectionItem]
		items_checked: DF.Int
		items_failed: DF.Int
		location: DF.Link | None
		naming_series: DF.Literal["HKINSP-.YYYY.-"]
		non_conformance: DF.Link | None
		open_findings: DF.Int
		passing_score: DF.Percent
		quality_procedure: DF.Link | None
		reinspection_of: DF.Link | None
		remarks: DF.SmallText | None
		score: DF.Percent
		signature: DF.Signature | None
		status: DF.Literal["Pending", "Accepted", "Rejected"]
		template: DF.Link
		trip_reference: DF.Data | None
	# end: auto-generated types

	# ------------------------------------------------------------------ validate
	def validate(self):
		self.validate_template()
		self.validate_reason()
		self.validate_reinspection()
		if not self.items:
			self.set_items_from_template()
		self.set_summary()
		if self.docstatus == 0:
			self.status = "Pending"

	def validate_template(self):
		template = frappe.get_cached_doc("Housekeeping Inspection Template", self.template)
		if template.disabled:
			frappe.throw(_("Inspection Template {0} is disabled.").format(frappe.bold(self.template)))
		if not self.quality_procedure:
			self.quality_procedure = template.quality_procedure
		self.passing_score = template.passing_score

	def validate_reason(self):
		self.inspection_reason = self.inspection_reason or "Routine"
		if self.inspection_reason == "Routine":
			self.trip_reference = None
			return
		if frappe.db.get_value("Housekeeping Area", self.housekeeping_area, "periodicity") != AS_NEEDED:
			frappe.throw(
				_("{0} inspections are only for As Needed areas (such as job trailers).").format(
					_(self.inspection_reason)
				)
			)

	def validate_reinspection(self):
		if not self.is_reinspection:
			self.reinspection_of = None
			return
		if not self.reinspection_of:
			frappe.throw(_("Select the original inspection in Re-inspection Of."))
		if self.reinspection_of == self.name:
			frappe.throw(_("An inspection cannot be a re-inspection of itself."))
		orig = frappe.db.get_value(
			"Housekeeping Inspection",
			self.reinspection_of,
			["housekeeping_area", "status", "docstatus"],
			as_dict=True,
		)
		if not orig or orig.docstatus != 1 or orig.status != "Rejected":
			frappe.throw(_("Re-inspection Of must be a submitted, Rejected inspection."))
		if orig.housekeeping_area != self.housekeeping_area:
			frappe.throw(
				_("Re-inspection must be for the same area ({0}).").format(frappe.bold(orig.housekeeping_area))
			)

	def set_items_from_template(self):
		self.set("items", [])
		for row in get_template_items(self.template):
			self.append("items", row)

	def set_summary(self):
		for row in self.items:
			if row.result != FAIL:
				row.corrected_on_spot = 0
		s = summarize(self.items, self.passing_score)
		self.score = s.score
		self.items_checked = s.items_checked
		self.items_failed = s.items_failed
		self.corrected_on_spot_count = s.corrected_on_spot_count
		self.open_findings = s.open_findings
		return s

	# ------------------------------------------------------------------ submit
	def before_submit(self):
		require_photo = frappe.db.get_value(
			"Housekeeping Inspection Template", self.template, "require_photo_on_fail"
		)
		errors = []
		for row in self.items:
			if not row.result:
				errors.append(_("Row {0}: Result is required for '{1}'.").format(row.idx, row.check_item))
			elif row.result == FAIL:
				if not cstr(row.finding).strip():
					errors.append(_("Row {0}: Finding is required for failed item '{1}'.").format(row.idx, row.check_item))
				if require_photo and not row.photo:
					errors.append(_("Row {0}: Photo is required for failed item '{1}'.").format(row.idx, row.check_item))
		if errors:
			frappe.throw("<br>".join(errors), title=_("Inspection Incomplete"))

		self.status = self.set_summary().status

	def on_submit(self):
		s = summarize(self.items, self.passing_score)
		if self.status == "Rejected":
			self.create_non_conformance(s)
		else:
			self.link_reinspection_to_original_nc()
		if not self.is_reinspection:
			self.update_area_schedule()
		update_area_housekeeping_status(self.housekeeping_area)

	def on_cancel(self):
		# Set on the instance (not the class): Frappe reads it via doc.get() when
		# checking back-links, so the Area / Non Conformance links don't block cancel.
		self.ignore_linked_doctypes = ("Non Conformance", "Housekeeping Area", "Housekeeping Inspection")
		self.db_set("status", "Pending")
		if self.non_conformance:
			nc = frappe.get_doc("Non Conformance", self.non_conformance)
			if nc.status == "Open":
				nc.status = "Cancelled"
				nc.flags.ignore_permissions = True
				nc.add_comment("Info", _("Cancelled because Housekeeping Inspection {0} was cancelled.").format(self.name))
				nc.save()
		if self.is_reinspection and self.reinspection_of:
			orig_nc = frappe.db.get_value("Housekeeping Inspection", self.reinspection_of, "non_conformance")
			if orig_nc and frappe.db.get_value("Non Conformance", orig_nc, "housekeeping_reinspection") == self.name:
				if frappe.db.get_value("Non Conformance", orig_nc, "status") == "Resolved":
					frappe.throw(
						_("Non Conformance {0} was resolved using this re-inspection. Reopen it before cancelling.").format(
							frappe.bold(orig_nc)
						)
					)
				frappe.db.set_value("Non Conformance", orig_nc, "housekeeping_reinspection", None)
		if not self.is_reinspection:
			refresh_area_last_inspection(self.housekeeping_area)
		update_area_housekeeping_status(self.housekeeping_area)

	# ------------------------------------------------------------------ helpers
	def update_area_schedule(self):
		area = frappe.get_doc("Housekeeping Area", self.housekeeping_area)
		inspected_on = getdate(self.inspection_date)
		values = {
			"last_inspection": self.name,
			"last_inspection_date": inspected_on,
			"last_score": self.score,
		}
		# Only move the schedule forward, never back (e.g. a late-entered older inspection)
		is_latest = not area.last_inspection_date or inspected_on >= getdate(area.last_inspection_date)
		if area.periodicity == AS_NEEDED:
			if not is_latest:
				return
			if self.inspection_reason == "Post-Return" and area.schedule_status != AWAITING_RETURN:
				frappe.msgprint(
					_("No Pre-Departure inspection was open for {0}. Post-Return recorded anyway.").format(
						frappe.bold(area.name)
					),
					indicator="orange",
				)
			values["schedule_status"] = trip_status(self.inspection_reason, area.schedule_status)
			frappe.db.set_value("Housekeeping Area", area.name, values)
			close_area_todos(area.name)
			return
		if is_latest:
			values["next_due_date"] = next_due(inspected_on, area.periodicity)
			values["schedule_status"] = schedule_status_for(values["next_due_date"])
		else:
			values = {}
		if values:
			frappe.db.set_value("Housekeeping Area", area.name, values)
		close_area_todos(area.name)

	def create_non_conformance(self, s):
		failed = [r for r in self.items if r.result == FAIL]
		rows = "".join(
			"<tr><td>" + escape_html(cstr(r.category)) + "</td><td>" + escape_html(cstr(r.check_item))
			+ "</td><td>" + (_("Yes") if r.is_critical else _("No"))
			+ "</td><td>" + (_("Yes") if r.corrected_on_spot else _("No"))
			+ "</td><td>" + escape_html(cstr(r.finding)) + "</td></tr>"
			for r in failed
		)
		details = (
			"<p>" + _("Area") + ": <b>" + escape_html(self.housekeeping_area) + "</b>"
			+ ((" (" + escape_html(cstr(self.location)) + ")") if self.location else "") + "<br>"
			+ _("Inspection") + ": <b>" + self.name + "</b> &ndash; " + cstr(self.inspection_date) + "<br>"
			+ _("Inspected By") + ": " + escape_html(cstr(self.inspector_name or self.inspected_by)) + "<br>"
			+ _("Score") + ": " + cstr(s.score) + "% (" + _("passing") + " " + cstr(flt(self.passing_score)) + "%)</p>"
			+ "<table class='table table-bordered'><thead><tr><th>" + _("Category") + "</th><th>" + _("Check Item")
			+ "</th><th>" + _("Critical") + "</th><th>" + _("Corrected on Spot") + "</th><th>" + _("Finding")
			+ "</th></tr></thead><tbody>" + rows + "</tbody></table>"
		)
		if s.severity == "Low":
			details += "<p>" + _("All failures were corrected on the spot, but the score was below passing. Address the root cause (staffing, storage capacity, cleaning schedule).") + "</p>"
		if self.remarks:
			details += "<p>" + _("Remarks") + ": " + escape_html(self.remarks) + "</p>"

		nc = frappe.get_doc({
			"doctype": "Non Conformance",
			"subject": "Housekeeping - " + self.housekeeping_area + " (" + self.name + ")",
			"procedure": self.quality_procedure,
			"status": "Open",
			"details": details,
			"housekeeping_area": self.housekeeping_area,
			"housekeeping_inspection": self.name,
			"severity": s.severity,
			"interim_control": _("Hazard barricaded or controlled pending correction.") if s.severity == "Critical" else None,
		})
		nc.flags.ignore_permissions = True
		nc.insert()
		self.db_set("non_conformance", nc.name)
		self.assign_to_area_owner(nc)

		frappe.msgprint(
			_("Non Conformance {0} created ({1}).").format(
				frappe.get_desk_link("Non Conformance", nc.name), _(s.severity)
			),
			indicator="red",
			alert=True,
		)

	def assign_to_area_owner(self, nc):
		if not self.area_owner:
			return
		user = frappe.db.get_value("Employee", self.area_owner, "user_id")
		if not user:
			return
		from frappe.desk.form.assign_to import add as assign

		assign({
			"assign_to": [user],
			"doctype": "Non Conformance",
			"name": nc.name,
			"description": _("Correct housekeeping findings in {0}").format(self.housekeeping_area),
			"priority": "High" if nc.severity == "Critical" else "Medium",
		}, ignore_permissions=True)

	def link_reinspection_to_original_nc(self):
		if not (self.is_reinspection and self.reinspection_of):
			return
		orig_nc = frappe.db.get_value("Housekeeping Inspection", self.reinspection_of, "non_conformance")
		if orig_nc:
			frappe.db.set_value("Non Conformance", orig_nc, "housekeeping_reinspection", self.name)
			frappe.msgprint(
				_("Re-inspection linked to {0}. Complete verification and resolve it to close the finding.").format(
					frappe.get_desk_link("Non Conformance", orig_nc)
				),
				indicator="green",
				alert=True,
			)


# ---------------------------------------------------------------------- API
@frappe.whitelist()
def get_template_items(template: str) -> list:
	doc = frappe.get_cached_doc("Housekeeping Inspection Template", template)
	doc.check_permission("read")
	return [{f: row.get(f) for f in TEMPLATE_ROW_FIELDS} for row in doc.items]


@frappe.whitelist()
def get_template_instructions(template: str) -> str:
	doc = frappe.get_cached_doc("Housekeeping Inspection Template", template)
	doc.check_permission("read")
	return doc.instructions or ""


def _template_for_area(area, reason=None):
	if reason == "Post-Return" and area.get("post_return_template"):
		return area.post_return_template
	return area.template


@frappe.whitelist()
def get_area_template(area: str, reason: str | None = None) -> str | None:
	doc = frappe.get_doc("Housekeeping Area", area)
	doc.check_permission("read")
	return _template_for_area(doc, reason)


def _fill_new_inspection(target, template=None):
	if template:
		target.template = template
	if target.template:
		target.quality_procedure, target.passing_score = frappe.db.get_value(
			"Housekeeping Inspection Template", target.template, ["quality_procedure", "passing_score"]
		)
		target.set("items", [])
		for row in get_template_items(target.template):
			target.append("items", row)
	if not target.inspected_by:
		target.inspected_by = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")


@frappe.whitelist()
def make_from_area(source_name: str, target_doc: str | dict | None = None):
	def postprocess(source, target):
		target.housekeeping_area = source.name
		reason = (frappe.flags.args or {}).get("reason")
		if source.periodicity == AS_NEEDED:
			reason = reason or ("Post-Return" if source.schedule_status == AWAITING_RETURN else "Pre-Departure")
			target.inspection_reason = reason
		else:
			target.inspection_reason = "Routine"
		_fill_new_inspection(target, _template_for_area(source, target.inspection_reason))

	return get_mapped_doc(
		"Housekeeping Area",
		source_name,
		{
			"Housekeeping Area": {
				"doctype": "Housekeeping Inspection",
				"validation": {"disabled": ["=", 0]},
				"field_map": {"location": "location", "department": "department", "area_owner": "area_owner", "company": "company"},
				"field_no_map": ["template", "inspector", "inspector_name", "naming_series"],
			}
		},
		target_doc,
		postprocess,
	)


@frappe.whitelist()
def make_reinspection(source_name: str, target_doc: str | dict | None = None):
	def postprocess(source, target):
		target.is_reinspection = 1
		target.reinspection_of = source.name
		target.status = "Pending"
		_fill_new_inspection(target)

	return get_mapped_doc(
		"Housekeeping Inspection",
		source_name,
		{
			"Housekeeping Inspection": {
				"doctype": "Housekeeping Inspection",
				"validation": {"docstatus": ["=", 1], "status": ["=", "Rejected"]},
				"field_no_map": [
					"status", "non_conformance", "signature", "remarks", "inspection_date", "score",
					"items_checked", "items_failed", "corrected_on_spot_count", "open_findings",
					"inspected_by", "inspector_name", "is_reinspection", "reinspection_of", "amended_from",
				],
			}
		},
		target_doc,
		postprocess,
	)


@frappe.whitelist()
def make_reinspection_from_nc(non_conformance: str):
	source = frappe.db.get_value("Non Conformance", non_conformance, "housekeeping_inspection")
	if not source:
		frappe.throw(_("This Non Conformance is not linked to a Housekeeping Inspection."))
	return make_reinspection(source)
