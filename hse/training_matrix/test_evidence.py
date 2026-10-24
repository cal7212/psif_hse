# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import UnitTestCase
from frappe.utils import getdate

from hse.training_matrix.evidence import resolve
from hse.training_matrix.lms import passes


def rec(name, date, counted=True, expires_on=None):
	return frappe._dict(name=name, date=getdate(date), counted=counted, expires_on=expires_on)


def ev(name, date, passed=True):
	return frappe._dict(name=name, date=getdate(date), passed=passed)


class UnitTestEvidence(UnitTestCase):
	def test_knowledge_course_qualified_by_latest_record(self):
		result = resolve([rec("R2", "2026-06-01"), rec("R1", "2025-06-01")], [], needs_eval=False)
		self.assertEqual((result["completed_on"], result["training_record"]), (getdate("2026-06-01"), "R2"))
		self.assertEqual(result["in_progress"], 0)

	def test_unacknowledged_record_is_in_progress(self):
		result = resolve(
			[rec("R2", "2026-06-01", counted=False), rec("R1", "2025-06-01")], [], needs_eval=False
		)
		self.assertEqual(result["training_record"], "R1")
		self.assertEqual(result["in_progress"], 1)

	def test_practical_course_needs_evaluation(self):
		result = resolve([rec("R1", "2026-06-01")], [], needs_eval=True)
		self.assertIsNone(result["completed_on"])
		self.assertEqual(result["in_progress"], 1)

	def test_passing_evaluation_qualifies(self):
		result = resolve([rec("R1", "2026-06-01")], [ev("E1", "2026-06-03")], needs_eval=True)
		self.assertEqual(
			(result["completed_on"], result["competency_evaluation"]), (getdate("2026-06-03"), "E1")
		)
		self.assertEqual((result["training_record"], result["in_progress"]), ("R1", 0))

	def test_failed_evaluation_after_pass_is_not_qualified(self):
		result = resolve(
			[rec("R1", "2026-06-01")], [ev("E2", "2026-07-01", False), ev("E1", "2026-06-03")], True
		)
		self.assertIsNone(result["completed_on"])
		self.assertEqual(result["in_progress"], 1)

	def test_prior_experience_evaluation_without_training(self):
		result = resolve([], [ev("E1", "2026-06-03")], needs_eval=False)
		self.assertEqual(result["competency_evaluation"], "E1")

	def test_certificate_expiry_comes_from_record(self):
		result = resolve([rec("R1", "2026-06-01", expires_on="2028-06-01")], [], needs_eval=False)
		self.assertEqual(result["expires_on"], "2028-06-01")

	def test_lms_quiz_pass_marks(self):
		scores = {"Q1": (82.0, 70.0), "Q2": (75.0, 70.0)}
		self.assertTrue(passes(scores, "LMS Completion Record"))  # quiz's own pass mark
		self.assertFalse(passes(scores, "Quiz (80%)"))  # TRN-700: 80% for quiz-verified courses
		self.assertTrue(passes({}, "Quiz (80%)"))  # a course with no quizzes


class UnitTestLmsHistoryClassify(UnitTestCase):
	def test_classify(self):
		from hse.training_matrix.lms_history import ALREADY, BELOW_PASS, NO_MATRIX, WILL_IMPORT, classify

		self.assertEqual(classify(True, False, True), WILL_IMPORT)
		self.assertEqual(classify(True, False, False), BELOW_PASS)
		self.assertEqual(classify(True, True, True), ALREADY)
		self.assertEqual(classify(False, False, True), NO_MATRIX)


def ft(name, date, passed=True, size="M"):
	return frappe._dict(
		name=name,
		date=getdate(date),
		passed=passed,
		manufacturer="3M",
		model="6502QL",
		style="Half",
		size=size,
	)


class UnitTestFitTestEvidence(UnitTestCase):
	def test_latest_pass_qualifies(self):
		from hse.training_matrix.evidence import resolve_fit_tests

		result = resolve_fit_tests([ft("T2", "2026-06-01"), ft("T1", "2025-06-01")])
		self.assertEqual(
			(result["completed_on"], result["respirator_fit_test"]), (getdate("2026-06-01"), "T2")
		)
		self.assertEqual(result["in_progress"], 0)

	def test_failed_retest_withdraws_the_respirator(self):
		from hse.training_matrix.evidence import resolve_fit_tests

		result = resolve_fit_tests([ft("T2", "2026-06-01", passed=False), ft("T1", "2025-06-01")])
		self.assertIsNone(result["completed_on"])
		self.assertEqual(result["in_progress"], 1)

	def test_other_respirator_keeps_the_course(self):
		from hse.training_matrix.evidence import resolve_fit_tests

		result = resolve_fit_tests([ft("T2", "2026-06-01", passed=False), ft("T1", "2026-05-01", size="L")])
		self.assertEqual(result["respirator_fit_test"], "T1")
		self.assertEqual(result["in_progress"], 1)

	def test_same_respirator_ignores_case_and_spacing(self):
		from hse.training_matrix.evidence import respirator_key

		self.assertEqual(
			respirator_key(ft("A", "2026-01-01")),
			respirator_key({**ft("B", "2026-01-01"), "model": " 6502ql "}),
		)
