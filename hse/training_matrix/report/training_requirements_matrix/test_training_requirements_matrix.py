# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.tests import UnitTestCase

from hse.training_matrix.report.training_requirements_matrix.training_requirements_matrix import total_rows


class UnitTestTrainingRequirementsMatrixTotals(UnitTestCase):
	def test_hours_per_role_and_missing_durations(self):
		data = [
			{"course": "SAF-0012", "duration_minutes": 26, "r_technician": "R", "r_manager": "R"},
			{"course": "SAF-0024", "duration_minutes": 0, "r_technician": "R", "r_manager": "C"},
			{"course": "SAF-0006", "duration_minutes": 45, "r_technician": "R", "r_manager": "—"},
		]
		required, conditional, missing = total_rows(data, ["Technician", "Manager"])
		self.assertEqual((required["r_technician"], required["r_manager"]), ("1.2", "0.4"))
		self.assertEqual((conditional["r_technician"], conditional["r_manager"]), ("—", "0.0"))
		self.assertEqual((missing["r_technician"], missing["r_manager"]), ("1", "1"))
		self.assertEqual(required["duration_minutes"], 71)

	def test_no_rows_no_totals(self):
		self.assertEqual(total_rows([], ["Technician"]), [])
