# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Which training evidence qualifies an employee for a course (TRN-700 Rev 1 §4.8, §4.13).

Evidence is a submitted TRN-702 Training Record (one attendee row per employee) or a submitted
TRN-704 Competency Evaluation. The matrix row is recalculated from the evidence whenever a record
or evaluation is submitted, cancelled or acknowledged, so the matrix never holds a completion the
records don't support.

- Knowledge-only courses (quiz, acknowledgment, completion record, certificate): the latest
  passing, acknowledged training record (or a passing evaluation) qualifies.
- Courses verified by practical demonstration, observation or a TRN-704 checklist: only a passing
  Competency Evaluation qualifies. Training without one leaves the row In Progress.
- Courses verified by "Respirator Fit Test" (OSHA 1910.134(f)): only a submitted Respirator Fit Test
  qualifies. A respirator counts while its latest test is a pass; the newest such pass is the
  completion date, so the annual refresher runs from it.
- Completion dates entered by hand (history loaded before Phase 2) are kept unless newer evidence
  replaces them.
"""

import frappe
from frappe.utils import getdate

# Verification methods that need a TRN-704 Competency Evaluation to rate the employee Qualified.
NEEDS_EVALUATION = {
	"Practical Demonstration",
	"Practical Evaluation",
	"Test and Practical",
	"Supervisor Observation",
	"TRN-704 Checklist",
	"Certificate and Observed Audit",
	"Quiz and MVR Review",
}
# Courses whose only evidence is a submitted Respirator Fit Test.
FIT_TEST = "Respirator Fit Test"
# Pass mark for quiz-verified courses (TRN-700 Rev 1 Appendix A).
QUIZ_PASS_MARK = 80
QUIZ_METHODS = {"Quiz (80%)", "Quiz and MVR Review"}
# Sources completed under the trainee's own login, so no separate acknowledgment is needed.
SELF_RECORDED = {"LMS Course", "External Certificate"}

MATRIX = "Employee Training Matrix"


def needs_evaluation(verification_method: str | None) -> bool:
	return verification_method in NEEDS_EVALUATION


def acknowledgment_required(source: str | None) -> bool:
	return source not in SELF_RECORDED


def training_records(employee: str, requirement: str) -> list[dict]:
	"""Submitted training records for the employee and course, newest first."""
	rows = frappe.get_all(
		"Training Record Attendee",
		filters={"employee": employee, "parenttype": "Training Record"},
		fields=["parent", "result", "acknowledged", "expires_on"],
	)
	if not rows:
		return []
	records = {
		r.name: r
		for r in frappe.get_all(
			"Training Record",
			filters={
				"name": ["in", list({r.parent for r in rows})],
				"docstatus": 1,
				"training_requirement": requirement,
			},
			fields=["name", "training_date", "source"],
		)
	}
	out = []
	for r in rows:
		rec = records.get(r.parent)
		if not rec or r.result == "Fail":
			continue
		out.append(
			frappe._dict(
				name=rec.name,
				date=getdate(rec.training_date),
				expires_on=r.expires_on,
				counted=bool(r.acknowledged or not acknowledgment_required(rec.source)),
			)
		)
	return sorted(out, key=lambda x: (x.date, x.name), reverse=True)


def evaluations(employee: str, requirement: str) -> list[dict]:
	return [
		frappe._dict(name=e.name, date=getdate(e.evaluation_date), passed=e.result == "Pass")
		for e in frappe.get_all(
			"Competency Evaluation",
			filters={"employee": employee, "training_requirement": requirement, "docstatus": 1},
			fields=["name", "evaluation_date", "result"],
			order_by="evaluation_date desc, creation desc",
		)
	]


def resolve(records: list[dict], evals: list[dict], needs_eval: bool) -> dict:
	"""Pure decision: qualified date, evidence links, expiry and in-progress flag."""
	counted = [r for r in records if r.counted]
	pending = [r for r in records if not r.counted]
	latest_eval = evals[0] if evals else None
	passed_eval = latest_eval if latest_eval and latest_eval.passed else None

	qualified_on, record, evaluation = None, None, None
	if needs_eval:
		if passed_eval:
			qualified_on, evaluation = passed_eval.date, passed_eval.name
			record = next((r for r in counted if r.date <= passed_eval.date), None)
	else:
		best_record = counted[0] if counted else None
		if best_record and (not passed_eval or best_record.date >= passed_eval.date):
			qualified_on, record = best_record.date, best_record
		elif passed_eval:
			qualified_on, evaluation = passed_eval.date, passed_eval.name

	newest_training = max((r.date for r in records), default=None)
	in_progress = bool(
		(pending and (qualified_on is None or pending[0].date > qualified_on))
		or (needs_eval and newest_training and (qualified_on is None or newest_training > qualified_on))
		or (
			latest_eval
			and not latest_eval.passed
			and (qualified_on is None or latest_eval.date >= qualified_on)
		)
	)
	return {
		"completed_on": qualified_on,
		"expires_on": record.expires_on if record else None,
		"training_record": record.name if record else None,
		"competency_evaluation": evaluation,
		"in_progress": 1 if in_progress else 0,
	}


def respirator_key(test) -> tuple:
	"""One respirator: the same make, model, style and size (case and spacing ignored)."""
	return tuple(
		" ".join(str(test.get(f) or "").upper().split()) for f in ("manufacturer", "model", "style", "size")
	)


def fit_tests(employee: str) -> list[dict]:
	"""Submitted fit tests for the employee, newest first."""
	return [
		frappe._dict(t, date=getdate(t.test_date), passed=t.result == "Pass")
		for t in frappe.get_all(
			FIT_TEST,
			filters={"employee": employee, "docstatus": 1},
			fields=["name", "test_date", "result", "manufacturer", "model", "style", "size"],
			order_by="test_date desc, creation desc",
		)
	]


def resolve_fit_tests(tests: list[dict]) -> dict:
	"""Pure decision for fit-test courses. tests: newest first.

	A respirator is current while its latest test passed; a later failed test on the same
	respirator withdraws it. The newest current pass qualifies the course."""
	latest = {}
	for t in tests:
		latest.setdefault(respirator_key(t), t)
	passed = sorted((t for t in latest.values() if t.passed), key=lambda t: (t.date, t.name), reverse=True)
	best = passed[0] if passed else None
	failed_since = any(not t.passed and (not best or t.date >= best.date) for t in latest.values())
	return {
		"completed_on": best.date if best else None,
		"expires_on": None,
		"training_record": None,
		"competency_evaluation": None,
		"respirator_fit_test": best.name if best else None,
		"in_progress": 1 if failed_since else 0,
	}


def recalculate(employee: str, requirement: str) -> None:
	"""Update the employee's matrix row for the course from its evidence."""
	if not frappe.db.exists(MATRIX, employee):
		return
	matrix = frappe.get_doc(MATRIX, employee)
	row = next((r for r in matrix.items if r.training_requirement == requirement), None)
	if not row:
		return
	verification = frappe.db.get_value("Training Requirement", requirement, "verification_method")
	if verification == FIT_TEST:
		result = resolve_fit_tests(fit_tests(employee))
	else:
		result = {
			**resolve(
				training_records(employee, requirement),
				evaluations(employee, requirement),
				needs_evaluation(verification),
			),
			"respirator_fit_test": None,
		}
	manual = bool(
		row.completed_on
		and not row.training_record
		and not row.competency_evaluation
		and not row.respirator_fit_test
	)
	if result["completed_on"] and not (manual and getdate(row.completed_on) > result["completed_on"]):
		row.update(result)  # evidence qualifies (and is at least as recent as any hand-entered date)
	elif manual:
		row.in_progress = result["in_progress"]  # keep the loaded history
	else:
		row.update({**result, "completed_on": None, "expires_on": None})  # evidence cancelled or failed
	matrix.flags.ignore_permissions = True
	matrix.save()


def recalculate_fit_test_courses(employee: str) -> None:
	"""Every course verified by a fit test (normally just one)."""
	for requirement in frappe.get_all(
		"Training Requirement", filters={"verification_method": FIT_TEST, "disabled": 0}, pluck="name"
	):
		recalculate(employee, requirement)
