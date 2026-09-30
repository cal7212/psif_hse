# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.tests import IntegrationTestCase, UnitTestCase

from hse.asset_inspection.doctype.asset_inspection.asset_inspection import (
	FAIL,
	PASS,
	evaluate_numeric,
)


class UnitTestAssetInspection(UnitTestCase):
	"""Pure logic tests; no database needed."""

	def test_numeric_within_limits(self):
		self.assertEqual(evaluate_numeric(50, 40, 60), PASS)

	def test_numeric_below_min(self):
		self.assertEqual(evaluate_numeric(30, 40, 60), FAIL)

	def test_numeric_above_max(self):
		self.assertEqual(evaluate_numeric(70, 40, 60), FAIL)

	def test_numeric_no_limits(self):
		self.assertEqual(evaluate_numeric(999), PASS)


class IntegrationTestAssetInspection(IntegrationTestCase):
	"""Add DB-backed tests here (requires Asset, Quality Procedure and Employee fixtures)."""

	pass
