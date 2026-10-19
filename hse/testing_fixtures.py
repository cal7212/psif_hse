# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Shared test fixtures: a fresh CI site may have no Company or Gender yet."""

import frappe

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
