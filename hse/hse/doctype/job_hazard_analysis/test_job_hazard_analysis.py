# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import today

from hse.hse.doctype.confined_space_permit.confined_space_permit import make_from_jha as csp_from_jha
from hse.hse.doctype.job_hazard_analysis.job_hazard_analysis import approval_errors, make_review, score_step
from hse.testing_fixtures import ensure_company, ensure_employee

JHA = "Job Hazard Analysis"


def step(idx=1, hazards="Hot oil", controls="Let cool", sev="3 - Moderate", lik="2 - Unlikely"):
	row = frappe._dict(
		idx=idx, job_step="Drain oil", hazards=hazards, controls=controls, severity=sev, likelihood=lik
	)
	score_step(row)
	return row


class UnitTestJobHazardAnalysis(UnitTestCase):
	def test_step_scoring(self):
		row = step()
		self.assertEqual((row.risk_score, row.risk_rating), (6, "Medium"))

	def test_approval_rules(self):
		base = frappe._dict(next_review_date="2027-01-01")
		self.assertEqual(approval_errors(frappe._dict(base, steps=[step()])), [])
		self.assertEqual(len(approval_errors(frappe._dict(base, steps=[]))), 1)
		self.assertEqual(len(approval_errors(frappe._dict(base, steps=[step(hazards="", controls=" ")]))), 2)
		critical = step(sev="5 - Catastrophic", lik="5 - Almost Certain")
		self.assertTrue(any("Critical" in e for e in approval_errors(frappe._dict(base, steps=[critical]))))
		self.assertEqual(len(approval_errors(frappe._dict(base, steps=[step(sev=None)]))), 1)


class IntegrationTestJobHazardAnalysis(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = ensure_company()
		cls.employee = ensure_employee("_Test JHA Preparer", cls.company)

	def make(self):
		return frappe.get_doc(
			{
				"doctype": JHA,
				"job_title": "_Test change HPU filter",
				"company": self.company,
				"prepared_by": self.employee,
				"req_confined_space": 1,
				"req_loto": 1,
				"steps": [
					{
						"job_step": "Lock out the HPU",
						"hazards": "Unexpected start-up",
						"controls": "LOTO per procedure",
						"severity": "4 - Major",
						"likelihood": "1 - Rare",
					}
				],
				"workers": [{"worker_name": "_Test Contractor", "employer": "Acme", "briefed": 1}],
			}
		).insert()

	def test_approve_review_and_permit(self):
		doc = self.make()
		self.assertEqual((doc.highest_risk_score, doc.highest_risk_rating), (4, "Low"))
		doc.submit()
		self.assertEqual(doc.status, "Active")
		permit = csp_from_jha(doc.name)
		self.assertEqual((permit.job_hazard_analysis, permit.iso_lockout), (doc.name, 1))
		review = make_review(doc.name)
		self.assertEqual(
			(review.revision, review.previous_analysis, str(review.analysis_date)), (2, doc.name, today())
		)
		self.assertEqual(review.workers[0].briefed, 0)
		review.insert()
		review.submit()
		doc.reload()
		self.assertEqual((doc.status, doc.superseded_by), ("Superseded", review.name))
