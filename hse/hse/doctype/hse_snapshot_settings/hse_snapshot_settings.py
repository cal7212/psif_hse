# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class HSESnapshotSettings(Document):
	def validate(self):
		if not 0 <= cint(self.send_hour) <= 23:
			frappe.throw(_("Send Hour must be 0 to 23."))
		seen = set()
		for r in self.recipients or []:
			if r.user:
				user = frappe.db.get_value("User", r.user, ["email", "enabled", "user_type"], as_dict=True)
				if not r.email and user:
					r.email = user.email
			if r.version == "Internal":
				if not r.user:
					frappe.throw(_("Row {0}: the Internal version needs a User.").format(r.idx))
				if not (user and user.enabled and user.user_type == "System User"):
					frappe.throw(
						_("Row {0}: {1} must be an enabled system user for the Internal version.").format(
							r.idx, r.user
						)
					)
				r.email = user.email
			key = (r.email or "").lower()
			if key in seen:
				frappe.throw(_("Row {0}: {1} is listed twice.").format(r.idx, r.email))
			seen.add(key)
