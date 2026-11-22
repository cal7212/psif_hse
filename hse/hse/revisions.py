# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Revisions of approved HSE documents (Risk Assessment, Job Hazard Analysis).

An approved document cannot change. Start Review copies it as a draft revision; approving the
revision marks the earlier one Superseded, and cancelling the revision puts the earlier one back
in force. Only one revision at a time may be replacing a document.

A document using RevisionMixin has the fields status (Draft / Active / Superseded / Cancelled),
revision, superseded_by, and the link to the earlier revision named by PREVIOUS_FIELD."""

import frappe
from frappe import _
from frappe.utils import add_months, cint, getdate

DRAFT, ACTIVE, SUPERSEDED, CANCELLED = "Draft", "Active", "Superseded", "Cancelled"


class RevisionMixin:
	PREVIOUS_FIELD = "previous_assessment"
	DATE_FIELD = "assessment_date"

	def previous_name(self):
		return self.get(self.PREVIOUS_FIELD)

	def validate_previous(self):
		prev_name = self.previous_name()
		if not prev_name:
			return
		prev = frappe.db.get_value(self.doctype, prev_name, ["docstatus", "status", "revision"], as_dict=True)
		if not prev or prev.docstatus != 1 or prev.status != ACTIVE:
			frappe.throw(
				_("{0} is not an approved {1} in force, so this revision cannot replace it.").format(
					prev_name, _(self.doctype)
				),
				title=_(self.doctype),
			)
		other = frappe.db.get_value(
			self.doctype,
			{self.PREVIOUS_FIELD: prev_name, "docstatus": ["<", 2], "name": ["!=", self.name or ""]},
			"name",
		)
		if other:
			frappe.throw(
				_("{0} is already being reviewed in {1}.").format(prev_name, other), title=_(self.doctype)
			)
		self.revision = cint(prev.revision) + 1

	def set_next_review_date(self):
		start = self.get(self.DATE_FIELD)
		if not self.next_review_date and start and cint(self.review_interval_months):
			self.next_review_date = add_months(start, cint(self.review_interval_months))
		self.validate_review_date()

	def validate_review_date(self):
		start = self.get(self.DATE_FIELD)
		if self.next_review_date and start and getdate(self.next_review_date) <= getdate(start):
			frappe.throw(
				_("Next Review Due must be after the {0}.").format(_(self.meta.get_label(self.DATE_FIELD))),
				title=_(self.doctype),
			)

	def supersede_previous(self):
		prev_name = self.previous_name()
		if not prev_name:
			return
		prev = frappe.get_doc(self.doctype, prev_name)
		prev.db_set({"status": SUPERSEDED, "superseded_by": self.name})
		prev.add_comment("Info", _("Superseded by {0} (revision {1}).").format(self.name, self.revision))

	def restore_previous(self):
		prev_name = self.previous_name()
		if not prev_name:
			return
		prev = frappe.db.get_value(self.doctype, prev_name, ["docstatus", "superseded_by"], as_dict=True)
		if prev and prev.docstatus == 1 and prev.superseded_by == self.name:
			frappe.db.set_value(self.doctype, prev_name, {"status": ACTIVE, "superseded_by": None})
			frappe.get_doc(self.doctype, prev_name).add_comment(
				"Info", _("Back in force: revision {0} was cancelled.").format(self.name)
			)

	def cancel_revision(self):
		"""Call from on_cancel."""
		# Must be set on the instance: the earlier revision links back to this one.
		self.ignore_linked_doctypes = (self.doctype,)
		self.db_set("status", CANCELLED)
		self.restore_previous()


def revision_postprocess(source, target, previous_field: str, date_field: str, today_value):
	"""Common set-up of a new revision made by get_mapped_doc."""
	target.revision = cint(source.revision) + 1
	target.set(previous_field, source.name)
	target.set(date_field, today_value)
