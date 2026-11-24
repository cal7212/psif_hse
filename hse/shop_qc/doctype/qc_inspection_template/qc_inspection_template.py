# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model import no_value_fields
from frappe.model.document import Document
from frappe.utils import cint, cstr, flt, now_datetime

# QM-400 6.3: authority to change controlled QMS documents rests with the Quality Manager.
TEMPLATE_AUTHORS = ("Quality Manager", "System Manager")
SYSTEM_CHANGE_SUMMARY = "Updated by a system patch or the sample-template installer."


def item_signature(items) -> list[tuple]:
	"""What a checklist says, line by line, ignoring row ids and timestamps."""
	if not items:
		return []
	meta = frappe.get_meta("QC Inspection Template Item")
	fields = [df.fieldname for df in meta.fields if df.fieldtype not in no_value_fields]
	return [tuple(cstr(row.get(f)) for f in fields) for row in items]


class QCInspectionTemplate(Document):
	def validate(self):
		self.model_prefix = (self.model_prefix or "").strip().upper() or None
		self.product_type = self.product_type or None
		if not self.quality_procedure and self.stage:
			shop = frappe.db.get_value("QC Stage", self.stage, "shop")
			if shop:
				self.quality_procedure = frappe.db.get_value("Build Shop", shop, "quality_procedure")
		for row in self.items:
			if not row.numeric:
				row.unit_spec_field = None
				row.min_value = row.max_value = 0
			else:
				row.unit_text_field = None  # numeric lines take limits, not text, from the unit
			if row.unit_spec_field:
				row.min_value = row.max_value = 0
				if flt(row.tolerance_minus_pct) < 0 or flt(row.tolerance_plus_pct) < 0:
					frappe.throw(_("Row {0}: tolerances must be positive percentages.").format(row.idx))
			if row.min_value and row.max_value and flt(row.min_value) > flt(row.max_value):
				frappe.throw(_("Row {0}: Min Value is greater than Max Value.").format(row.idx))
		self.control_revision()

	def control_revision(self):
		"""QM-400 6.3 / 7.5.2: a change to the checklist is a new, approved revision with a
		summary of what changed. Inspections record the revision they were done to."""
		system = frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch
		if self.is_new():
			self.revision = cint(self.revision) or 1
			self.stamp_approval()
			return
		before = self.get_doc_before_save()
		if not before or item_signature(before.items) == item_signature(self.items):
			return
		if not system and not set(frappe.get_roles()) & set(TEMPLATE_AUTHORS):
			frappe.throw(
				_("Only a Quality Manager can change the checklist lines of an inspection template."),
				title=_("Controlled Document"),
			)
		summary_changed = cstr(self.change_summary).strip() and self.has_value_changed("change_summary")
		if not summary_changed:
			if not system:
				frappe.throw(
					_("Enter a Change Summary describing this revision."), title=_("Change Summary Required")
				)
			self.change_summary = self.flags.change_summary or SYSTEM_CHANGE_SUMMARY
		self.revision = cint(before.revision) + 1
		self.stamp_approval()
		self.add_comment(
			"Info",
			_("Revision {0}: {1}").format(self.revision, cstr(self.change_summary).strip()),
		)

	def stamp_approval(self):
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()
