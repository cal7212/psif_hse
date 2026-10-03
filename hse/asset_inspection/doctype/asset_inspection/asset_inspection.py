# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cstr, escape_html, flt, getdate, nowdate

from hse.asset_inspection.utils import update_asset_safety_status
from hse.hse.instruments import add_used_instruments, check_listed_instruments, listed_instruments

PASS, FAIL, NA = "Pass", "Fail", "N/A"
TEMPLATE_ROW_FIELDS = (
	"check_item",
	"criteria",
	"is_critical",
	"numeric",
	"min_value",
	"max_value",
	"uom",
)


def evaluate_numeric(reading_value, min_value=None, max_value=None):
	"""Return Pass/Fail for a numeric reading against optional limits.
	A limit of 0/None is treated as 'not set'."""
	value = flt(reading_value)
	if min_value and value < flt(min_value):
		return FAIL
	if max_value and value > flt(max_value):
		return FAIL
	return PASS


class AssetInspection(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hse.asset_inspection.doctype.asset_inspection_reading.asset_inspection_reading import (
			AssetInspectionReading,
		)

		amended_from: DF.Link | None
		asset: DF.Link | None
		asset_category: DF.Link | None
		asset_maintenance_log: DF.Link | None
		asset_name: DF.Data | None
		company: DF.Link | None
		inspected_by: DF.Link | None
		inspection_date: DF.Datetime | None
		inspector_name: DF.Data | None
		is_reinspection: DF.Check
		items: DF.Table[AssetInspectionReading]
		location: DF.Link | None
		naming_series: DF.Literal["AINSP-.YYYY.-"]
		non_conformance: DF.Link | None
		quality_procedure: DF.Link | None
		reinspection_of: DF.Link | None
		remarks: DF.SmallText | None
		signature: DF.Signature | None
		status: DF.Literal["Pending", "Accepted", "Rejected"]
		template: DF.Link | None
	# end: auto-generated types

	# ------------------------------------------------------------------ validate
	def validate(self):
		self.validate_template()
		self.validate_maintenance_log()
		self.validate_reinspection()
		if not self.items:
			self.set_items_from_template()
		self.evaluate_numeric_readings()
		self.sync_instruments()
		if self.docstatus == 0:
			self.status = "Pending"

	def sync_instruments(self):
		"""Default the per-reading instrument when only one is listed, and list every
		instrument a reading uses in the Test Equipment table."""
		names = listed_instruments(self)
		only = names[0] if len(names) == 1 else None
		for r in self.items:
			if r.numeric and not r.instrument and only:
				r.instrument = only
		add_used_instruments(self, [r.instrument for r in self.items])

	def validate_template(self):
		template = frappe.get_cached_doc("Asset Inspection Template", self.template)
		if template.disabled:
			frappe.throw(_("Inspection Template {0} is disabled.").format(frappe.bold(self.template)))
		if template.asset_category and self.asset_category and template.asset_category != self.asset_category:
			frappe.throw(
				_("Template {0} is for Asset Category {1}, but asset {2} is {3}.").format(
					frappe.bold(self.template),
					frappe.bold(template.asset_category),
					frappe.bold(self.asset),
					frappe.bold(self.asset_category),
				)
			)
		if not self.quality_procedure:
			self.quality_procedure = template.quality_procedure

	def validate_maintenance_log(self):
		if not self.asset_maintenance_log:
			return
		log_asset, log_docstatus = frappe.db.get_value(
			"Asset Maintenance Log", self.asset_maintenance_log, ["asset_name", "docstatus"]
		)
		if log_asset != self.asset:
			frappe.throw(
				_("Maintenance Log {0} belongs to asset {1}, not {2}.").format(
					frappe.bold(self.asset_maintenance_log), frappe.bold(log_asset), frappe.bold(self.asset)
				)
			)
		if log_docstatus == 2:
			frappe.throw(
				_("Maintenance Log {0} is cancelled.").format(frappe.bold(self.asset_maintenance_log))
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
			"Asset Inspection", self.reinspection_of, ["asset", "status", "docstatus"], as_dict=True
		)
		if not orig or orig.docstatus != 1 or orig.status != "Rejected":
			frappe.throw(_("Re-inspection Of must be a submitted, Rejected inspection."))
		if orig.asset != self.asset:
			frappe.throw(_("Re-inspection must be for the same asset ({0}).").format(frappe.bold(orig.asset)))

	def set_items_from_template(self):
		self.set("items", [])
		for row in get_template_items(self.template):
			self.append("items", row)

	def evaluate_numeric_readings(self):
		# Float fields default to 0, so a 0 reading is treated as "not entered".
		# A genuine zero reading should be marked Fail by the inspector.
		for row in self.items:
			if row.numeric and row.result != NA and flt(row.reading_value) != 0:
				row.result = evaluate_numeric(row.reading_value, row.min_value, row.max_value)

	# ------------------------------------------------------------------ submit
	def before_submit(self):
		errors = []
		for row in self.items:
			if not row.result:
				errors.append(_("Row {0}: Result is required for '{1}'.").format(row.idx, row.check_item))
			elif row.result == FAIL and not cstr(row.finding).strip():
				errors.append(
					_("Row {0}: Finding is required for failed item '{1}'.").format(row.idx, row.check_item)
				)
			if row.numeric and row.result == PASS and flt(row.reading_value) == 0:
				errors.append(_("Row {0}: Enter the reading for '{1}'.").format(row.idx, row.check_item))
		if errors:
			frappe.throw("<br>".join(errors), title=_("Inspection Incomplete"))
		self.check_test_equipment()

		self.status = "Rejected" if self.get_failed_rows() else "Accepted"

	def check_test_equipment(self):
		needs = any(r.numeric and r.result != NA and flt(r.reading_value) for r in self.items)
		if not needs and not self.instruments:
			return
		if not self.instruments:
			frappe.throw(
				_("Add the test equipment used for the numeric readings."), title=_("Test Equipment")
			)
		errors = check_listed_instruments(self, self.inspection_date)
		for r in self.items:
			if r.numeric and r.result != NA and flt(r.reading_value) and not r.instrument:
				errors.append(_("Row {0}: select the instrument used for '{1}'.").format(r.idx, r.check_item))
		if errors:
			frappe.throw("<br>".join(errors), title=_("Test Equipment"))

	def on_submit(self):
		if self.status == "Rejected":
			self.create_non_conformance()
			self.link_to_maintenance_log()
		else:
			self.complete_maintenance_log()
			self.link_reinspection_to_original_nc()
		update_asset_safety_status(self.asset)

	def on_cancel(self):
		# Must be set on the instance (not the class): Frappe reads it via doc.get()
		# when checking back-links after on_cancel. Lets an inspection be cancelled
		# even though its Maintenance Log / Non Conformance link back to it.
		self.ignore_linked_doctypes = ("Non Conformance", "Asset Maintenance Log", "Asset Inspection")
		self.db_set("status", "Pending")
		if (
			self.asset_maintenance_log
			and frappe.db.get_value("Asset Maintenance Log", self.asset_maintenance_log, "asset_inspection")
			== self.name
		):
			frappe.db.set_value("Asset Maintenance Log", self.asset_maintenance_log, "asset_inspection", None)
		if self.non_conformance:
			nc = frappe.get_doc("Non Conformance", self.non_conformance)
			if nc.status == "Open":
				nc.status = "Cancelled"
				nc.flags.ignore_permissions = True
				nc.add_comment(
					"Info", _("Cancelled because Asset Inspection {0} was cancelled.").format(self.name)
				)
				nc.save()
		if self.is_reinspection and self.reinspection_of:
			orig_nc = frappe.db.get_value("Asset Inspection", self.reinspection_of, "non_conformance")
			if orig_nc and frappe.db.get_value("Non Conformance", orig_nc, "reinspection") == self.name:
				if frappe.db.get_value("Non Conformance", orig_nc, "status") == "Resolved":
					frappe.throw(
						_(
							"Non Conformance {0} was resolved using this re-inspection. Reopen it before cancelling."
						).format(frappe.bold(orig_nc))
					)
				frappe.db.set_value("Non Conformance", orig_nc, "reinspection", None)
		update_asset_safety_status(self.asset)

	# ------------------------------------------------------------------ helpers
	def get_failed_rows(self):
		return [r for r in self.items if r.result == FAIL]

	def create_non_conformance(self):
		failed = self.get_failed_rows()
		critical = any(r.is_critical for r in failed)

		rows = "".join(
			"<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td></tr>".format(
				escape_html(cstr(r.check_item)),
				_("Yes") if r.is_critical else _("No"),
				escape_html(cstr(r.reading_value)) if r.numeric else "",
				escape_html(cstr(r.finding)),
			)
			for r in failed
		)
		details = (
			f"<p>{_('Asset')}: <b>{escape_html(self.asset)}</b> ({escape_html(cstr(self.asset_name))})<br>"
			f"{_('Inspection')}: <b>{self.name}</b> &ndash; {self.inspection_date}<br>"
			f"{_('Inspected By')}: {escape_html(cstr(self.inspector_name or self.inspected_by))}</p>"
			f"<table class='table table-bordered'><thead><tr><th>{_('Check Item')}</th><th>{_('Critical')}</th>"
			f"<th>{_('Reading')}</th><th>{_('Finding')}</th></tr></thead><tbody>{rows}</tbody></table>"
		)
		if self.remarks:
			details += f"<p>{_('Remarks')}: {escape_html(self.remarks)}</p>"

		nc = frappe.get_doc(
			{
				"doctype": "Non Conformance",
				"subject": f"Inspection failure - {self.asset_name or self.asset} ({self.name})",
				"procedure": self.quality_procedure,
				"status": "Open",
				"details": details,
				"asset": self.asset,
				"asset_inspection": self.name,
				"severity": "Critical" if critical else "Medium",
				"interim_control": _("Asset tagged Out of Service pending corrective action.")
				if critical
				else None,
			}
		)
		nc.flags.ignore_permissions = True
		nc.insert()

		self.db_set("non_conformance", nc.name)
		nc_link = frappe.get_desk_link("Non Conformance", nc.name)
		frappe.msgprint(
			_("Non Conformance {0} created and asset placed Out of Service.").format(nc_link)
			if critical
			else _("Non Conformance {0} created.").format(nc_link),
			indicator="red",
			alert=True,
		)

	def link_to_maintenance_log(self):
		if self.asset_maintenance_log:
			frappe.db.set_value(
				"Asset Maintenance Log", self.asset_maintenance_log, "asset_inspection", self.name
			)

	def complete_maintenance_log(self):
		if not self.asset_maintenance_log:
			return
		log = frappe.get_doc("Asset Maintenance Log", self.asset_maintenance_log)
		if log.docstatus != 0:
			frappe.db.set_value("Asset Maintenance Log", log.name, "asset_inspection", self.name)
			return

		log.maintenance_status = "Completed"
		log.completion_date = (
			getdate(self.inspection_date)
			if getdate(self.inspection_date) <= getdate(nowdate())
			else nowdate()
		)
		log.asset_inspection = self.name
		note = _("Completed by Asset Inspection {0} (Accepted).").format(self.name)
		log.actions_performed = f"{log.actions_performed}<br>{note}" if log.actions_performed else note
		log.flags.ignore_permissions = True

		if log.get("has_certificate") and not log.get("certificate_attachement"):
			log.save()
			frappe.msgprint(
				_(
					"Maintenance Log {0} marked Completed but not submitted: attach the required certificate and submit it."
				).format(frappe.get_desk_link("Asset Maintenance Log", log.name)),
				indicator="orange",
			)
		else:
			log.submit()  # updates next due date on the Asset Maintenance task

	def link_reinspection_to_original_nc(self):
		if not (self.is_reinspection and self.reinspection_of):
			return
		orig_nc = frappe.db.get_value("Asset Inspection", self.reinspection_of, "non_conformance")
		if orig_nc:
			frappe.db.set_value("Non Conformance", orig_nc, "reinspection", self.name)
			frappe.msgprint(
				_(
					"Re-inspection linked to {0}. Complete verification and resolve it to return the asset to service."
				).format(frappe.get_desk_link("Non Conformance", orig_nc)),
				indicator="green",
				alert=True,
			)


# ---------------------------------------------------------------------- API
@frappe.whitelist()
def get_template_items(template: str):
	doc = frappe.get_cached_doc("Asset Inspection Template", template)
	doc.check_permission("read")
	return [{f: row.get(f) for f in TEMPLATE_ROW_FIELDS} for row in doc.items]


@frappe.whitelist()
def get_template_instructions(template: str):
	doc = frappe.get_cached_doc("Asset Inspection Template", template)
	doc.check_permission("read")
	return doc.instructions or ""


def _fill_new_inspection(target, template=None):
	if template:
		target.template = template
	if target.asset:
		target.asset_name = frappe.db.get_value("Asset", target.asset, "asset_name")
	if target.template:
		target.quality_procedure = frappe.db.get_value(
			"Asset Inspection Template", target.template, "quality_procedure"
		)
		target.set("items", [])
		for row in get_template_items(target.template):
			target.append("items", row)
	if not target.inspected_by:
		target.inspected_by = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")


@frappe.whitelist()
def make_from_maintenance_log(source_name: str, target_doc: str | dict | None = None):
	def postprocess(source, target):
		target.naming_series = "AINSP-.YYYY.-"
		target.asset = source.asset_name  # Asset Maintenance Log.asset_name is the Asset link
		template = None
		if source.task:
			template = frappe.db.get_value("Asset Maintenance Task", source.task, "inspection_template")
		_fill_new_inspection(target, template)

	return get_mapped_doc(
		"Asset Maintenance Log",
		source_name,
		{
			"Asset Maintenance Log": {
				"doctype": "Asset Inspection",
				"validation": {"docstatus": ["=", 0]},
				"field_map": {"name": "asset_maintenance_log"},
				"field_no_map": ["asset_name", "description", "naming_series"],
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
		"Asset Inspection",
		source_name,
		{
			"Asset Inspection": {
				"doctype": "Asset Inspection",
				"validation": {"docstatus": ["=", 1], "status": ["=", "Rejected"]},
				"field_no_map": [
					"status",
					"non_conformance",
					"signature",
					"remarks",
					"inspection_date",
					"inspected_by",
					"inspector_name",
					"is_reinspection",
					"reinspection_of",
					"amended_from",
				],
			}
		},
		target_doc,
		postprocess,
	)


@frappe.whitelist()
def make_reinspection_from_nc(non_conformance: str):
	source = frappe.db.get_value("Non Conformance", non_conformance, "asset_inspection")
	if not source:
		frappe.throw(_("This Non Conformance is not linked to an Asset Inspection."))
	return make_reinspection(source)
