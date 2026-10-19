# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import UnitTestCase

from hse.training_matrix import permissions


class UnitTestMatrixPermissions(UnitTestCase):
	def test_full_access_never_denies(self):
		"""Frappe treats any falsy answer from a has_permission hook (None included) as a denial."""
		doc = frappe._dict(employee="EMP-OTHER")
		self.assertIs(permissions.matrix_has_permission(doc, "read", "Administrator"), True)
