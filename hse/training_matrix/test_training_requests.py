# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.tests import UnitTestCase
from frappe.utils import getdate

from hse.training_matrix.training_requests import add_business_days


class UnitTestBusinessDays(UnitTestCase):
	def test_skips_weekends(self):
		# Friday 2026-10-23 + 10 business days = Friday 2026-11-06
		self.assertEqual(add_business_days("2026-10-23", 10), getdate("2026-11-06"))
		# Saturday start counts from the following Monday
		self.assertEqual(add_business_days("2026-10-24", 1), getdate("2026-10-26"))
