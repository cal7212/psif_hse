# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ManagerHomeSettings(Document):
	def validate(self):
		self.home_page = (self.home_page or "").strip() or "/app/executive-dashboard"
		if not (self.home_page.startswith("/app/") or self.home_page.startswith("/desk")):
			frappe.throw(_("Home Page must be a desk path starting with /app/ or /desk."))
