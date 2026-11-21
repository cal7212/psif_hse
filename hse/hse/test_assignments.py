# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hse.hse.assignments import assign
from hse.hse.email_settings import EMAIL_SETTINGS as SETTINGS

USER = "_t_assignee@example.com"


def set_switch(value: int) -> None:
	frappe.db.set_single_value(SETTINGS, "assignment_emails", value)
	frappe.clear_document_cache(SETTINGS, SETTINGS)


class IntegrationTestAssignments(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("User", USER):
			frappe.get_doc(
				{"doctype": "User", "email": USER, "first_name": "Assignee", "send_welcome_email": 0}
			).insert(ignore_permissions=True)

	def make_note(self, title):
		return frappe.get_doc({"doctype": "Note", "title": title, "public": 1}).insert()

	def notifications(self, note):
		return frappe.db.count(
			"Notification Log",
			{"for_user": USER, "type": "Assignment", "document_type": "Note", "document_name": note.name},
		)

	def test_switch_off_assigns_without_notifying(self):
		set_switch(0)
		try:
			note = self.make_note("_T quiet assignment")
			self.assertEqual(assign([USER], "Note", note.name, "Check this"), [USER])
			self.assertTrue(
				frappe.db.exists(
					"ToDo",
					{
						"reference_type": "Note",
						"reference_name": note.name,
						"allocated_to": USER,
						"status": "Open",
					},
				)
			)
			self.assertEqual(self.notifications(note), 0)
			# a second call does not duplicate the open ToDo
			self.assertEqual(assign([USER], "Note", note.name, "Check this"), [])
		finally:
			set_switch(1)

	def test_switch_on_notifies(self):
		set_switch(1)
		note = self.make_note("_T notified assignment")
		assign([USER], "Note", note.name, "Check this")
		self.assertEqual(self.notifications(note), 1)
