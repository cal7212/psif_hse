# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.tests import UnitTestCase
from frappe.utils import getdate

from hse.training_matrix import status as st

HIRE_30 = {"initial_due_basis": st.HIRE, "initial_due_days": 30, "refresher_frequency": "Annually"}
ON_ASSIGNMENT = {"initial_due_basis": st.ASSIGNED, "initial_due_days": 0, "refresher_frequency": "Annually"}
PER_CERT = {
	"initial_due_basis": st.ASSIGNED,
	"initial_due_days": 0,
	"refresher_frequency": st.PER_CERTIFICATION,
}
TODAY = "2026-10-05"


def row(**kw):
	return {"requirement_code": st.REQUIRED, "assigned_on": "2026-10-01", **kw}


class UnitTestTrainingStatus(UnitTestCase):
	def test_new_hire_course_due_within_30_days(self):
		self.assertEqual(st.evaluate(row(), HIRE_30, "2026-10-01", TODAY)["status"], st.DUE)

	def test_new_hire_course_past_deadline_is_overdue(self):
		result = st.evaluate(row(), HIRE_30, "2026-08-01", TODAY)
		self.assertEqual((result["status"], result["qualification"]), (st.OVERDUE, st.NOT_QUALIFIED))

	def test_far_deadline_not_started(self):
		req = {**HIRE_30, "initial_due_days": 90}
		self.assertEqual(st.evaluate(row(), req, "2026-10-01", TODAY)["status"], st.NOT_STARTED)

	def test_in_progress(self):
		self.assertEqual(
			st.evaluate(row(in_progress=1), HIRE_30, "2026-10-01", TODAY)["status"], st.IN_PROGRESS
		)

	def test_completed_annual_is_qualified_until_refresher(self):
		result = st.evaluate(row(completed_on="2026-01-10"), ON_ASSIGNMENT, None, TODAY)
		self.assertEqual(result["status"], st.COMPLETED)
		self.assertEqual(result["qualification"], st.QUALIFIED)
		self.assertEqual(result["due_date"], getdate("2027-01-10"))

	def test_refresher_due_soon_stays_qualified(self):
		result = st.evaluate(row(completed_on="2025-11-01"), ON_ASSIGNMENT, None, TODAY)
		self.assertEqual((result["status"], result["qualification"]), (st.DUE, st.QUALIFIED))

	def test_lapsed_refresher_is_not_qualified(self):
		result = st.evaluate(row(completed_on="2025-09-01"), ON_ASSIGNMENT, None, TODAY)
		self.assertEqual((result["status"], result["qualification"]), (st.OVERDUE, st.NOT_QUALIFIED))

	def test_certificate_expiry(self):
		current = st.evaluate(row(completed_on="2025-01-01", expires_on="2027-01-01"), PER_CERT, None, TODAY)
		expired = st.evaluate(row(completed_on="2025-01-01", expires_on="2026-10-04"), PER_CERT, None, TODAY)
		self.assertEqual(current["status"], st.COMPLETED)
		self.assertEqual((expired["status"], expired["qualification"]), (st.OVERDUE, st.NOT_QUALIFIED))

	def test_conditional_needs_confirmation(self):
		self.assertEqual(
			st.evaluate(row(requirement_code=st.CONDITIONAL), ON_ASSIGNMENT, None, TODAY)["status"],
			st.CONFIRM,
		)
		not_applicable = st.evaluate(
			row(requirement_code=st.CONDITIONAL, applicability=st.DOES_NOT_APPLY), ON_ASSIGNMENT, None, TODAY
		)
		self.assertEqual(not_applicable["status"], st.NOT_APPLICABLE)
		applies = st.evaluate(
			row(requirement_code=st.CONDITIONAL, applicability=st.APPLIES), ON_ASSIGNMENT, None, TODAY
		)
		self.assertEqual(applies["is_required"], 1)

	def test_history_kept_when_no_longer_required(self):
		result = st.evaluate(
			row(requirement_code=st.NOT_REQUIRED, completed_on="2026-05-01"), ON_ASSIGNMENT, None, TODAY
		)
		self.assertEqual(
			(result["status"], result["qualification"], result["is_required"]),
			(st.NOT_APPLICABLE, st.QUALIFIED, 0),
		)

	def test_percent_complete_matches_appendix_a(self):
		rows = [
			{"is_required": 1, "qualification": st.QUALIFIED},
			{"is_required": 1, "qualification": st.NOT_QUALIFIED},
			{"is_required": 0, "qualification": st.NOT_QUALIFIED},
		]
		self.assertEqual(st.percent_complete(rows), 50.0)

	def test_part_2_codes(self):
		self.assertEqual(st.matrix_code(st.COMPLETED, "2026-01-05"), "C 01/05/26")
		self.assertEqual(st.matrix_code(st.OVERDUE), "OD")
		self.assertEqual(st.matrix_code(st.NOT_APPLICABLE), "—")

	def test_frequency_summary(self):
		self.assertEqual(
			st.frequency_summary(st.HIRE, 0, "Annually", 0, "new chemical hazard"),
			"Upon hire; annually; new chemical hazard",
		)
		self.assertEqual(
			st.frequency_summary(st.ASSIGNED, 0, "Every 3 Years"), "Upon assignment; every 3 years"
		)


class UnitTestRetrainingStatus(UnitTestCase):
	def row(self, **kw):
		return {"requirement_code": st.REQUIRED, "assigned_on": "2026-01-01", **kw}

	def test_earlier_training_holds_until_retraining_due(self):
		r = st.evaluate(
			self.row(completed_on="2026-03-01", retrain_from="2026-10-10", retrain_due="2026-11-01"),
			ON_ASSIGNMENT,
			None,
			"2026-10-15",
		)
		self.assertEqual((r["status"], r["qualification"]), (st.DUE, st.QUALIFIED))

	def test_missed_retraining_is_overdue(self):
		r = st.evaluate(
			self.row(completed_on="2026-03-01", retrain_from="2026-10-10", retrain_due="2026-11-01"),
			ON_ASSIGNMENT,
			None,
			"2026-11-02",
		)
		self.assertEqual((r["status"], r["qualification"]), (st.OVERDUE, st.NOT_QUALIFIED))

	def test_retraining_done(self):
		r = st.evaluate(
			self.row(completed_on="2026-10-20", retrain_from="2026-10-10", retrain_due="2026-11-01"),
			ON_ASSIGNMENT,
			None,
			"2026-11-02",
		)
		self.assertEqual(r["status"], st.COMPLETED)
