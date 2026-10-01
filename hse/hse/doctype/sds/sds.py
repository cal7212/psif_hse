# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_years, get_link_to_form, getdate, nowdate

RETENTION_YEARS = 30  # 29 CFR 1910.1020(d)(1)(ii)(B): identity, where used, when used
REVIEW_INTERVAL_YEARS = 1  # internal practice: confirm each active SDS is current yearly


def summarize_use(rows):
	"""Return (in_use, first_used, last_used, retention_until) from SDS Location rows.

	A row with no end date means the chemical is still in use there. Retention runs
	30 years from the last end date once the chemical is out of use everywhere."""
	if not rows:
		return 0, None, None, None
	starts = [getdate(r.get("start_date")) for r in rows if r.get("start_date")]
	in_use = int(any(not r.get("end_date") for r in rows))
	first_used = min(starts) if starts else None
	if in_use:
		return 1, first_used, None, None
	last_used = max(getdate(r.get("end_date")) for r in rows)
	return 0, first_used, last_used, add_years(last_used, RETENTION_YEARS)


class SDS(Document):
	def validate(self):
		self.title = (self.product_name or "").strip()
		self.upc = (self.upc or "").strip() or None
		self.validate_locations()
		self.apply_status_rules()
		self.update_use_summary()
		self.update_review_date()
		self.validate_supersedes()
		self.warn_duplicates()

	def validate_locations(self):
		for row in self.locations:
			if row.end_date and row.start_date and getdate(row.end_date) < getdate(row.start_date):
				frappe.throw(
					_("Row {0}: Use End Date cannot be before Use Start Date.").format(row.idx),
					title=_("Invalid Dates"),
				)

	def apply_status_rules(self):
		if self.status == "Discontinued":
			self.discontinued_date = self.discontinued_date or nowdate()
			for row in self.locations:
				if not row.end_date:
					row.end_date = self.discontinued_date
		elif self.status == "Active":
			self.discontinued_date = None
			if self.superseded_by:
				frappe.throw(
					_(
						"This SDS was superseded by {0}. Open that version instead of reactivating this one."
					).format(frappe.bold(self.superseded_by))
				)

	def update_use_summary(self):
		self.in_use, self.first_used_date, self.last_used_date, self.retention_until = summarize_use(
			[r.as_dict() for r in self.locations]
		)

	def update_review_date(self):
		self.next_review_date = (
			add_years(getdate(self.last_reviewed_on), REVIEW_INTERVAL_YEARS)
			if self.last_reviewed_on
			else None
		)

	def validate_supersedes(self):
		if not self.supersedes:
			return
		if self.supersedes == self.name:
			frappe.throw(_("An SDS cannot supersede itself."))
		other = frappe.db.get_value("SDS", self.supersedes, ["superseded_by"], as_dict=True)
		if other and other.superseded_by and other.superseded_by != self.name:
			frappe.throw(
				_("{0} is already superseded by {1}.").format(
					frappe.bold(self.supersedes), frappe.bold(other.superseded_by)
				)
			)

	def warn_duplicates(self):
		if self.status != "Active" or not self.product_name:
			return
		dupes = frappe.get_all(
			"SDS",
			filters={
				"product_name": self.product_name.strip(),
				"manufacturer_name": (self.manufacturer_name or "").strip(),
				"status": "Active",
				"name": ["!=", self.name or ""],
			},
			pluck="name",
		)
		if dupes:
			frappe.msgprint(
				_(
					"Another active SDS exists for this product and manufacturer: {0}. Consider using New Version or marking one Superseded."
				).format(", ".join(get_link_to_form("SDS", d) for d in dupes)),
				indicator="orange",
				alert=True,
			)

	def on_update(self):
		if self.supersedes and self.status == "Active":
			self.mark_previous_superseded()

	def mark_previous_superseded(self):
		old = frappe.get_doc("SDS", self.supersedes)
		if old.superseded_by == self.name and old.status == "Superseded":
			return
		today = nowdate()
		old.status = "Superseded"
		old.superseded_by = self.name
		for row in old.locations:
			if not row.end_date:
				row.end_date = today
		old.flags.ignore_permissions = True
		old.add_comment("Info", _("Superseded by {0}").format(self.name))
		old.save()

	def on_trash(self):
		if self.locations or self.superseded_by or self.supersedes:
			frappe.throw(
				_(
					"This SDS has a use or version history and must be kept for {0} years. Set its status to Discontinued or Superseded instead of deleting it."
				).format(RETENTION_YEARS),
				title=_("Retention Required"),
			)


@frappe.whitelist()
def make_new_version(source_name: str):
	"""Copy an SDS into a new draft version. Current locations carry over;
	saving the new version marks the old one Superseded and closes its locations."""
	source = frappe.get_doc("SDS", source_name)
	source.check_permission("read")
	if source.superseded_by:
		frappe.throw(_("{0} is already superseded by {1}.").format(source.name, source.superseded_by))

	new = frappe.copy_doc(source)
	new.status = "Active"
	new.supersedes = source.name
	new.superseded_by = None
	new.attach_sds = None
	new.version_date = None
	new.sds_uploaded = 0
	new.last_reviewed_on = None
	new.reviewed_by = None
	new.discontinued_date = None
	today = nowdate()
	new.set("locations", [])
	for row in source.locations:
		if not row.end_date:
			new.append(
				"locations",
				{
					"location": row.location,
					"storage_detail": row.storage_detail,
					"quantity": row.quantity,
					"container_size": row.container_size,
					"uom": row.uom,
					"container_type": row.container_type,
					"start_date": today,
				},
			)
	return new.as_dict()


@frappe.whitelist()
def mark_reviewed(name: str):
	doc = frappe.get_doc("SDS", name)
	doc.check_permission("write")
	doc.last_reviewed_on = nowdate()
	doc.reviewed_by = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	doc.save()
	return doc.next_review_date
