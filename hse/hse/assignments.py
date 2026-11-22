# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""ToDo assignments that PSIF IMS makes on its own: overdue training, training requests, skills
ready for authorization, failed competency evaluations and housekeeping findings.

assign() works like the desk's Assign To (frappe.desk.form.assign_to.add): one open ToDo per
person, the document shared with anyone who could not otherwise open it, and the Assigned To
field set where the document has one. PSIF IMS Email Settings → ToDo Assignment Emails is
the app-wide switch for telling the person about it: on, they get the
usual bell notification and email (each person's Notification Settings still apply) and follow
the document if they follow assigned documents; off, the ToDo is made without any of that.
Assignments people make by hand in the desk are not affected.
"""

import frappe
import frappe.share
from frappe import _
from frappe.desk.form.assign_to import notify_assignment
from frappe.desk.form.document_follow import _follow_document
from frappe.utils import nowdate

from hse.hse.email_settings import email_enabled


def assign(
	users,
	doctype: str,
	name: str,
	description: str,
	priority: str = "Medium",
) -> list[str]:
	"""Give each user an open ToDo on the document unless they already have one. Returns the
	users who got a new ToDo."""
	notify = email_enabled("assignment_emails")
	assigned_by = frappe.session.user
	added = []
	for user in dict.fromkeys(u for u in users or [] if u):
		if frappe.db.exists(
			"ToDo",
			{"reference_type": doctype, "reference_name": name, "allocated_to": user, "status": "Open"},
		):
			continue
		frappe.get_doc(
			{
				"doctype": "ToDo",
				"allocated_to": user,
				"reference_type": doctype,
				"reference_name": str(name),
				"description": description or _("Assignment for {0} {1}").format(doctype, name),
				"priority": priority,
				"status": "Open",
				"date": nowdate(),
				"assigned_by": assigned_by,
			}
		).insert(ignore_permissions=True)
		added.append(user)

		if frappe.get_meta(doctype).get_field("assigned_to"):
			frappe.db.set_value(doctype, name, "assigned_to", user)
		doc = frappe.get_doc(doctype, name)
		if not frappe.has_permission(doc=doc, user=user) and not frappe.get_system_settings(
			"disable_document_sharing"
		):
			frappe.share.add_docshare(doctype, str(name), user, flags={"ignore_share_permission": True})

		if not notify:
			continue
		if frappe.get_cached_value("User", user, "follow_assigned_documents"):
			_follow_document(doctype, name, user)
		notify_assignment(assigned_by, user, doctype, name, action="ASSIGN", description=description)
	return added
