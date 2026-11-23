# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Shared test fixtures: a fresh CI site may have no Company or Gender yet."""

import frappe

TEST_GENDER = "_T Gender"


def ensure_company() -> str:
	"""Return an existing Company, loading ERPNext's Company test records if the site has none.

	A bare Company insert fails on a fresh CI site (no Warehouse Types, fiscal year, etc.),
	and finishing the setup wizard collides with ERPNext's own test records."""
	company = frappe.db.get_value("Company", {}, "name")
	if company:
		return company
	from frappe.tests.utils import make_test_records

	make_test_records("Company")
	return frappe.db.get_value("Company", {}, "name")


def ensure_gender() -> str:
	"""Return an existing Gender, creating a test one if the site has none."""
	gender = frappe.db.get_value("Gender", {}, "name")
	if gender:
		return gender
	return frappe.get_doc({"doctype": "Gender", "gender": TEST_GENDER}).insert(ignore_permissions=True).name


def ensure_employee(first_name: str, company: str | None = None) -> str:
	"""Return an active test Employee named first_name, creating it if needed (no user)."""
	name = frappe.db.get_value("Employee", {"first_name": first_name, "status": "Active"}, "name")
	if name:
		return name
	return (
		frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": first_name,
				"gender": ensure_gender(),
				"date_of_birth": "1990-01-01",
				"date_of_joining": "2020-01-01",
				"company": company or ensure_company(),
				"status": "Active",
			}
		)
		.insert(ignore_permissions=True)
		.name
	)
