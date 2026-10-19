# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Shared test fixtures: a fresh CI site may have no Company or Gender yet."""

import frappe
from frappe.utils import now_datetime

TEST_COMPANY = "_T HSE Company"
TEST_GENDER = "_T Gender"


def ensure_company() -> str:
	"""Return an existing Company, creating a test one if the site has none."""
	company = frappe.db.get_value("Company", {}, "name")
	if company:
		return company
	return (
		frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": TEST_COMPANY,
				"abbr": "_THC",
				"default_currency": "USD",
				"country": "United States",
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def ensure_gender() -> str:
	"""Return an existing Gender, creating a test one if the site has none."""
	gender = frappe.db.get_value("Gender", {}, "name")
	if gender:
		return gender
	return frappe.get_doc({"doctype": "Gender", "gender": TEST_GENDER}).insert(ignore_permissions=True).name


def before_tests():
	"""bench run-tests hook: finish the ERPNext setup wizard on a fresh CI site.

	Creating a Company directly fails there (no Warehouse Types, fiscal year, etc.)."""
	frappe.clear_cache()
	if not frappe.get_list("Company"):
		from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

		year = now_datetime().year
		setup_complete(
			{
				"currency": "USD",
				"full_name": "Test User",
				"company_name": TEST_COMPANY,
				"timezone": "America/New_York",
				"company_abbr": "_THC",
				"industry": "Manufacturing",
				"country": "United States",
				"fy_start_date": f"{year}-01-01",
				"fy_end_date": f"{year}-12-31",
				"language": "english",
				"company_tagline": "Testing",
				"email": "test@example.com",
				"password": "test",
				"chart_of_accounts": "Standard",
			}
		)
	frappe.db.commit()  # nosemgrep
