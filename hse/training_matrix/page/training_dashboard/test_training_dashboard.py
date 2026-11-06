# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import add_days, getdate, today

from hse.quality_metrics.metrics import METRICS, calculate
from hse.testing_fixtures import ensure_company, ensure_gender
from hse.training_matrix import dashboard_data as dd
from hse.training_matrix import status as st
from hse.training_matrix.doctype.employee_training_matrix.test_employee_training_matrix import (
	make_designation,
	make_requirement,
	make_role,
)
from hse.training_matrix.matrix import sync_matrix
from hse.training_matrix.page.training_dashboard.training_dashboard import get_dashboard

DESIG, ROLE, SKILL, COURSE = "_T Dash Designation", "_T Dash Role", "_T Dash Skill", "_T-DASH-SK"
NEW_METRICS = (
	"training_due_30",
	"training_employees_overdue",
	"skill_maps_at_risk",
	"skill_authorizations_expiring",
)


class UnitTestComingDue(UnitTestCase):
	def test_window(self):
		now = getdate()
		row = frappe._dict(status=st.DUE, due_date=add_days(now, 10))
		self.assertTrue(dd.is_coming_due(row, now, 30))
		self.assertFalse(dd.is_coming_due(row, now, 5))
		self.assertFalse(dd.is_coming_due(frappe._dict(status=st.OVERDUE, due_date=now), now, 30))
		self.assertFalse(dd.is_coming_due(frappe._dict(status=st.COMPLETED, due_date=now), now, 30))
		self.assertFalse(dd.is_coming_due(frappe._dict(status=st.NOT_STARTED, due_date=None), now, 30))


class IntegrationTestTrainingDashboard(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.setup.doctype.employee.test_employee import make_employee

		make_designation(DESIG)
		make_role(ROLE, DESIG)
		make_requirement(COURSE, roles=[(ROLE, st.REQUIRED)], basis=st.ASSIGNED, days=10)
		if not frappe.db.exists("Skill", SKILL):
			frappe.get_doc({"doctype": "Skill", "skill_name": SKILL}).insert()
		if not frappe.db.exists("Skill Definition", SKILL):
			frappe.get_doc(
				{
					"doctype": "Skill Definition",
					"skill": SKILL,
					"courses": [{"training_requirement": COURSE}],
					"roles": [{"training_role": ROLE, "requirement_code": st.REQUIRED}],
				}
			).insert()
		cls.employee = make_employee(
			"_t_training_dashboard@example.com",
			company=ensure_company(),
			gender=ensure_gender(),
			designation=DESIG,
			date_of_joining=add_days(today(), -5),
		)
		cls.matrix = sync_matrix(cls.employee)

	def test_coming_due_and_skill_map_at_risk(self):
		row = next(r for r in self.matrix.items if r.training_requirement == COURSE)
		self.assertIn(row.status, (st.DUE, st.NOT_STARTED))
		due = dd.coming_due_rows(None, 30)
		self.assertIn((self.matrix.name, COURSE), {(r.parent, r.training_requirement) for r in due})
		self.assertIn(SKILL, [s.skill for s in self.matrix.skills])
		maps = dd.skill_maps(None, 30)
		hits = [r for r in maps["rows"] if r["matrix"] == self.matrix.name and r["skill"] == SKILL]
		self.assertTrue(hits)
		self.assertEqual(hits[0]["kind"], "coming_due")
		summary = next(s for s in maps["skills"] if s["skill"] == SKILL)
		self.assertGreaterEqual(summary["at_risk"], 1)
		self.assertIn(COURSE, summary["courses"])
		self.assertIn((self.matrix.name, SKILL), dd.skill_maps_at_risk(None, 30))
		# Outside a 5-day window the course is not yet coming due.
		self.assertNotIn(
			(self.matrix.name, SKILL), {(r["matrix"], r["skill"]) for r in dd.skill_maps(None, 5)["rows"]}
		)

	def test_get_dashboard_returns_sections(self):
		frappe.set_user("Administrator")
		data = get_dashboard("last_90_days", 60)
		self.assertEqual(data["horizon"], 60)
		self.assertTrue(data["can_read"])
		for key in (
			"headline",
			"attention",
			"coming_due",
			"skills",
			"by_course",
			"by_department",
			"employees",
			"metrics",
			"reviews",
		):
			self.assertIn(key, data)
		self.assertEqual(len(data["headline"]), 6)
		self.assertIn(SKILL, [s["skill"] for s in data["skills"]["skills"]])
		self.assertEqual(get_dashboard("bogus", 7)["horizon"], 30)

	def test_new_metrics_calculate(self):
		for key in NEW_METRICS:
			self.assertIn(key, METRICS)
			value, _detail = calculate(key, "2026-01-01", "2026-01-31")
			self.assertIsInstance(value, int, key)
		self.assertGreaterEqual(calculate("training_due_30", None, None)[0], 1)
		self.assertGreaterEqual(calculate("skill_maps_at_risk", None, None)[0], 1)
