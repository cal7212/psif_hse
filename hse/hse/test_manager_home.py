# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from hse.hse import manager_home as mh
from hse.testing_fixtures import ensure_company, ensure_gender

BOSS = "mh-boss@example.com"
STAFF = "mh-staff@example.com"
EXTRA = "mh-extra@example.com"


def _user(email):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
		).insert(ignore_permissions=True)
		frappe.get_doc("User", email).add_roles("Employee")
	return email


class IntegrationTestManagerHome(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		for u in (BOSS, STAFF, EXTRA):
			_user(u)
		self.s = frappe.get_doc(mh.SETTINGS)
		self.s.enabled = 1
		self.s.include_direct_reports = 1
		self.s.include_system_managers = 1
		self.s.home_page = mh.DEFAULT_HOME
		self.s.set("include_users", [])
		self.s.set("exclude_users", [])
		self.s.save()
		self._boss_employee()

	def _boss_employee(self):
		company = ensure_company()

		def emp(user, reports_to=None):
			name = frappe.db.get_value("Employee", {"user_id": user})
			if name:
				return name
			doc = frappe.get_doc(
				{
					"doctype": "Employee",
					"first_name": user.split("@")[0],
					"gender": ensure_gender(),
					"date_of_birth": "1990-01-01",
					"date_of_joining": "2020-01-01",
					"company": company,
					"user_id": user,
					"status": "Active",
					"reports_to": reports_to,
				}
			)
			doc.insert(ignore_permissions=True)
			return doc.name

		boss = emp(BOSS)
		emp(STAFF, boss)

	def test_direct_reports_and_admin(self):
		self.assertEqual(mh.home_for(BOSS), mh.DEFAULT_HOME)
		self.assertIsNone(mh.home_for(STAFF))
		self.assertIsNone(mh.home_for("Administrator"))
		self.assertIsNone(mh.home_for("Guest"))

	def test_include_exclude_and_disable(self):
		self.s.append("include_users", {"user": EXTRA})
		self.s.save()
		self.assertEqual(mh.home_for(EXTRA), mh.DEFAULT_HOME)
		self.s.append("exclude_users", {"user": EXTRA})
		self.s.append("exclude_users", {"user": BOSS})
		self.s.save()
		self.assertIsNone(mh.home_for(EXTRA))
		self.assertIsNone(mh.home_for(BOSS))
		self.s.set("exclude_users", [])
		self.s.include_direct_reports = 0
		self.s.save()
		self.assertIsNone(mh.home_for(BOSS))
		self.s.include_direct_reports = 1
		self.s.enabled = 0
		self.s.save()
		self.assertIsNone(mh.home_for(BOSS))

	def test_preview_and_login_flag(self):
		data = mh.preview()
		users = {u["user"] for u in data["users"]}
		self.assertIn(BOSS, users)
		self.assertNotIn(STAFF, users)
		self.assertNotIn("Administrator", users)
		frappe.set_user(BOSS)
		frappe.local.flags.home_page = None
		mh.on_session_creation()
		self.assertEqual(frappe.local.flags.home_page, mh.DEFAULT_HOME)
		frappe.local.flags.home_page = None
		frappe.set_user("Administrator")

	def test_home_page_must_be_desk_path(self):
		self.s.home_page = "https://example.com"
		self.assertRaises(frappe.ValidationError, self.s.save)
