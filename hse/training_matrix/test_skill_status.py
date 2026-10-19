# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from frappe.tests import UnitTestCase

from hse.training_matrix import skill_status as ss

DEFS = {
	"Mechanical": {"courses": ["M1", "SAF-0011"], "prerequisites": []},
	"Technician": {"courses": ["T1"], "prerequisites": ["Mechanical"]},
	"Hose Building": {"courses": ["H1"], "prerequisites": []},
}
ALL = {"M1", "SAF-0011", "T1"}


def evaluate(qualified, state=None, auths=None, on_date="2026-10-05", skills=("Technician",)):
	return ss.evaluate(DEFS, skills, set(qualified), set(), state or {}, auths or {}, on_date)


class UnitTestSkillStatus(UnitTestCase):
	def test_prerequisites_evaluated_first(self):
		self.assertEqual(list(evaluate(set())), ["Mechanical", "Technician"])

	def test_progress(self):
		self.assertEqual(evaluate(set())["Technician"]["status"], ss.NOT_STARTED)
		self.assertEqual(evaluate({"M1"})["Mechanical"]["status"], ss.IN_TRAINING)

	def test_courses_make_eligible_but_manager_grants(self):
		r = evaluate(ALL)
		self.assertEqual(r["Mechanical"]["status"], ss.READY)
		self.assertEqual(r["Technician"]["status"], ss.IN_TRAINING)  # Mechanical not yet authorized
		self.assertIn("Mechanical (skill)", r["Technician"]["missing"])

	def test_authorized_prerequisite_unlocks_next_rung(self):
		auths = {"Mechanical": [{"name": "A1", "date": "2026-10-05"}]}
		r = evaluate(ALL, {"Mechanical": {"eligible_since": "2026-10-05"}}, auths)
		self.assertEqual(r["Mechanical"]["status"], ss.AUTHORIZED)
		self.assertEqual(r["Technician"]["status"], ss.READY)

	def test_lapse_cascades_and_needs_reauthorization(self):
		auths = {
			"Mechanical": [{"name": "A1", "date": "2026-10-05"}],
			"Technician": [{"name": "A2", "date": "2026-10-06"}],
		}
		state = {
			"Mechanical": {"eligible_since": "2026-10-05"},
			"Technician": {"eligible_since": "2026-10-06"},
		}
		lapsed = evaluate({"M1", "T1"}, state, auths, "2026-11-01")
		self.assertEqual(
			(lapsed["Mechanical"]["status"], lapsed["Technician"]["status"]), (ss.LAPSED, ss.LAPSED)
		)
		requalified = evaluate(ALL, {"Mechanical": {"eligible_since": None}}, auths, "2026-11-10")
		self.assertEqual(requalified["Mechanical"]["status"], ss.READY)  # old authorization no longer counts

	def test_expired_authorization(self):
		r = ss.evaluate(
			DEFS,
			["Hose Building"],
			{"H1"},
			set(),
			{"Hose Building": {"eligible_since": "2026-01-01"}},
			{"Hose Building": [{"name": "A3", "date": "2026-01-02", "expires_on": "2026-10-01"}]},
			"2026-10-05",
		)
		self.assertEqual(r["Hose Building"]["status"], ss.READY)

	def test_skill_courses_include_prerequisites(self):
		self.assertEqual(ss.skill_courses(DEFS, "Technician"), ["M1", "SAF-0011", "T1"])

	def test_circular_prerequisites(self):
		with self.assertRaises(ValueError):
			ss.dependency_order({"A": {"prerequisites": ["B"]}, "B": {"prerequisites": ["A"]}}, ["A"])
