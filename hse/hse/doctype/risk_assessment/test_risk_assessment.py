# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import add_days, add_months, getdate, today

from hse.hse.doctype.risk_assessment.risk_assessment import (
	action_errors,
	approval_errors,
	assign_due_reviews,
	hazard_errors,
	level,
	make_review,
	risk_rating,
	risk_score,
	risk_summary,
	score_hazard,
)
from hse.hse.page.hse_dashboard.hse_dashboard import att_risk_actions_overdue, att_risk_reviews_due
from hse.hse.report.risk_register.risk_register import execute as risk_register
from hse.testing_fixtures import ensure_company, ensure_employee

RA = "Risk Assessment"


def hazard(idx=1, sev="4 - Major", lik="3 - Possible", controls=None, rsev=None, rlik=None, ctype=None):
	row = frappe._dict(
		idx=idx,
		hazard="Pinch point",
		initial_severity=sev,
		initial_likelihood=lik,
		additional_controls=controls,
		residual_severity=rsev,
		residual_likelihood=rlik,
		control_type=ctype,
	)
	score_hazard(row)
	return row


class UnitTestRiskAssessment(UnitTestCase):
	def test_level_parsing(self):
		self.assertEqual(level("3 - Possible"), 3)
		self.assertEqual(level("5"), 5)
		self.assertEqual(level(""), 0)
		self.assertEqual(level(None), 0)
		self.assertEqual(level("9 - Off scale"), 0)

	def test_score_and_bands(self):
		self.assertEqual(risk_score("4 - Major", "3 - Possible"), 12)
		self.assertEqual(risk_score("4 - Major", None), 0)
		expected = {
			0: "",
			1: "Low",
			4: "Low",
			5: "Medium",
			9: "Medium",
			10: "High",
			16: "High",
			20: "Critical",
			25: "Critical",
		}
		for score, rating in expected.items():
			self.assertEqual(risk_rating(score), rating, score)

	def test_residual_is_initial_without_controls(self):
		row = hazard(rsev="1 - Negligible", rlik="1 - Rare")  # ignored: no additional controls
		self.assertEqual((row.initial_score, row.residual_score), (12, 12))
		self.assertEqual(row.residual_rating, "High")
		row = hazard(controls="Guard fitted", rsev="4 - Major", rlik="1 - Rare", ctype="Engineering Controls")
		self.assertEqual((row.residual_score, row.residual_rating), (4, "Low"))

	def test_controls_cannot_raise_risk(self):
		row = hazard(
			sev="2 - Minor", lik="2 - Unlikely", controls="x", rsev="3 - Moderate", rlik="3 - Possible"
		)
		self.assertEqual(len(hazard_errors([row])), 1)

	def test_complete_ratings_needed_to_approve(self):
		row = hazard(sev=None, controls="Guard fitted")
		errors = hazard_errors([row], complete=True)
		self.assertEqual(len(errors), 3)  # initial rating, residual rating, control type

	def test_approval_rules(self):
		base = frappe._dict(next_review_date="2027-01-01", residual_risk_acceptance=None)
		critical = hazard(sev="5 - Catastrophic", lik="4 - Likely")
		self.assertTrue(any("Critical" in e for e in approval_errors(frappe._dict(base, hazards=[critical]))))
		high = hazard()
		self.assertTrue(any("Acceptance" in e for e in approval_errors(frappe._dict(base, hazards=[high]))))
		self.assertEqual(
			approval_errors(
				frappe._dict(base, hazards=[high], residual_risk_acceptance="Supervised; permit")
			),
			[],
		)
		low = hazard(controls="Guard", rsev="4 - Major", rlik="1 - Rare", ctype="Engineering Controls")
		self.assertEqual(approval_errors(frappe._dict(base, hazards=[low])), [])
		self.assertEqual(len(approval_errors(frappe._dict(base, hazards=[]))), 1)
		self.assertEqual(len(approval_errors(frappe._dict(base, hazards=[low], next_review_date=None))), 1)

	def test_summary_and_action_rows(self):
		rows = [hazard(1), hazard(2, sev="1 - Negligible", lik="2 - Unlikely")]
		s = risk_summary(rows)
		self.assertEqual((s["hazard_count"], s["highest_residual_score"], s["high_risk_count"]), (2, 12, 1))
		self.assertEqual(s["highest_residual_rating"], "High")
		actions = [frappe._dict(idx=1, hazard_no=2), frappe._dict(idx=2, hazard_no=3), frappe._dict(idx=3)]
		self.assertEqual(len(action_errors(actions, 2)), 1)


class IntegrationTestRiskAssessment(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = ensure_company()
		cls.employee = ensure_employee("_Test RA Assessor", cls.company)

	def make(self, submit=True, **kw):
		doc = frappe.get_doc(
			{
				"doctype": RA,
				"title": "_Test press brake operation",
				"company": self.company,
				"assessed_by": self.employee,
				"assessment_date": today(),
				"hazards": [
					{
						"hazard_category": "Mechanical / Moving Parts",
						"hazard": "Hand in die area",
						"initial_severity": "4 - Major",
						"initial_likelihood": "3 - Possible",
						"additional_controls": "Light curtain",
						"control_type": "Engineering Controls",
						"residual_severity": "4 - Major",
						"residual_likelihood": "1 - Rare",
					}
				],
				**kw,
			}
		).insert()
		if submit:
			doc.submit()
		return doc

	def test_draft_scores_and_review_date(self):
		doc = self.make(submit=False)
		self.assertEqual(doc.status, "Draft")
		self.assertEqual(getdate(doc.next_review_date), getdate(add_months(today(), 12)))
		self.assertEqual((doc.hazards[0].initial_score, doc.hazards[0].residual_rating), (12, "Low"))
		self.assertEqual(doc.highest_initial_rating, "High")

	def test_high_residual_needs_acceptance(self):
		doc = self.make(submit=False)
		doc.hazards[0].additional_controls = None
		doc.save()
		self.assertRaises(frappe.ValidationError, doc.submit)
		doc.reload()
		doc.residual_risk_acceptance = "Two-person operation under supervision"
		doc.submit()
		self.assertEqual((doc.status, doc.approved_by), ("Active", frappe.session.user))

	def test_actions_after_approval(self):
		doc = self.make(
			actions=[{"hazard_no": 1, "title": "Fit light curtain", "date_due": add_days(today(), -2)}],
		)
		self.assertEqual(getdate(doc.date_due), getdate(add_days(today(), -2)))
		self.assertTrue(att_risk_actions_overdue())
		doc.actions[0].date_done = today()
		doc.save()
		self.assertIsNone(doc.date_due)
		self.assertEqual(getdate(doc.date_done), getdate(today()))

	def test_review_supersedes_and_cancel_restores(self):
		first = self.make(actions=[{"title": "Open action"}, {"title": "Done", "date_done": today()}])
		review = make_review(first.name)
		self.assertEqual((review.revision, review.previous_assessment), (2, first.name))
		self.assertEqual(len(review.hazards), 1)
		self.assertEqual([a.title for a in review.actions], ["Open action"])
		review.insert()
		self.assertRaises(frappe.ValidationError, make_review(first.name).insert)  # one review at a time
		review.submit()
		first.reload()
		self.assertEqual((first.status, first.superseded_by), ("Superseded", review.name))
		self.assertRaises(frappe.ValidationError, make_review, first.name)  # not in force any more
		review.cancel()
		first.reload()
		self.assertEqual((first.status, first.superseded_by), ("Active", None))

	def test_register_and_reviews_due(self):
		doc = self.make()
		_cols, rows = risk_register({"company": self.company})
		self.assertIn(doc.name, [r.risk_assessment for r in rows])
		_cols, rows = risk_register({"company": self.company, "min_residual_rating": "High"})
		self.assertNotIn(doc.name, [r.risk_assessment for r in rows])
		doc.db_set("next_review_date", add_days(today(), -1))
		self.assertTrue(att_risk_reviews_due())
		assign_due_reviews()  # the assessor has no user: falls back to Safety Managers, if any
