# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Respirator skills.

Respirator Wearer: respirator training (SAF-0017) plus a current passed fit test (SAF-0017A).
Respirator Fit Tester: fit-test administration (SAF-0017B, practical evaluation); an in-house
tester must hold it, authorized and current, to submit a Respirator Fit Test.

Taking SAF-0017 alone does not qualify anyone to wear a respirator. Employees put in the
"Respirator Users" Employee Group get the Respirator Wearer skill through the Training Role of the
same name; the skill brings in both courses, and only a manager's Skill Authorization grants it
once both are current.

Existing records are left as they are, so edits made in Frappe are never overwritten.
"""

import frappe

from hse.training_matrix.evidence import FIT_TEST
from hse.training_matrix.install import SAFETY_MANAGER, make_roles
from hse.training_matrix.matrix import enqueue_resync
from hse.training_matrix.status import ASSIGNED

TRAINING = "SAF-0017"
FIT_TEST_COURSE = "SAF-0017A"
TESTER_COURSE = "SAF-0017B"
GROUP = ROLE = "Respirator Users"
SKILL = "Respirator Wearer"
TESTER_GROUP = TESTER_ROLE = "Respirator Fit Testers"
TESTER_SKILL = "Respirator Fit Tester"


def _insert(values: dict) -> None:
	doc = frappe.get_doc(values)
	doc.flags.skip_resync = True
	doc.insert(ignore_permissions=True)


COURSES = {
	FIT_TEST_COURSE: {
		"course_title": "Respirator Fit Test",
		"delivery_method": "Fit test (qualitative or quantitative)",
		"verification_method": FIT_TEST,
		"frequency_notes": "before first use; when the respirator or the employee's physical condition changes",
	},
	TESTER_COURSE: {
		"course_title": "Respirator Fit Test Administration",
		"delivery_method": "Instructor-led and hands-on",
		"verification_method": "Practical Evaluation",
		"frequency_notes": "when protocols or instruments change",
	},
}
SKILLS = {
	SKILL: {
		"skill_description": "Qualified to wear a tight-fitting respirator: medically cleared, trained and fit tested.",
		"description": "Needs current respirator training and a current passed fit test. Name the approved "
		"respirator(s) in the Skill Authorization scope.",
		"courses": (TRAINING, FIT_TEST_COURSE),
		"role": ROLE,
	},
	TESTER_SKILL: {
		"skill_description": "Qualified to administer respirator fit tests (OSHA 1910.134 Appendix A).",
		"description": "Needs a current, passed practical evaluation in fit-test administration (OSHA 1910.134 "
		"Appendix A): prepare test agents, set up and check the instrument, run the protocol and recognize "
		"invalid tests. Name the "
		"protocols and instruments in the Skill Authorization scope. An in-house tester must hold this "
		"skill to submit a Respirator Fit Test.",
		"courses": (TESTER_COURSE,),
		"role": TESTER_ROLE,
		"authorizer_role": SAFETY_MANAGER,
	},
}
ROLES = {ROLE: GROUP, TESTER_ROLE: TESTER_GROUP}


def create_course(course_id: str) -> bool:
	if frappe.db.exists("Training Requirement", course_id):
		return False
	_insert(
		{
			"doctype": "Training Requirement",
			"course_id": course_id,
			"avenue": "Safety / EHS",
			"initial_due_basis": ASSIGNED,
			"initial_due_days": 0,
			"refresher_frequency": "Annually",
			**COURSES[course_id],
		}
	)
	return True


def create_role(role: str) -> bool:
	if frappe.db.exists("Training Role", role):
		return False
	group = ROLES[role]
	values = {"doctype": "Training Role", "role_name": role}
	if frappe.db.exists("DocType", "Employee Group"):
		if not frappe.db.exists("Employee Group", group):
			frappe.get_doc({"doctype": "Employee Group", "employee_group_name": group}).insert(
				ignore_permissions=True
			)
		values["employee_groups"] = [{"employee_group": group}]
	_insert(values)
	return True


def create_skill(skill: str) -> bool:
	if not frappe.db.exists("DocType", "Skill") or frappe.db.exists("Skill Definition", skill):
		return False
	spec = SKILLS[skill]
	if not frappe.db.exists("Skill", skill):
		frappe.get_doc(
			{"doctype": "Skill", "skill_name": skill, "description": spec["skill_description"]}
		).insert(ignore_permissions=True)
	courses = [c for c in spec["courses"] if frappe.db.exists("Training Requirement", c)]
	_insert(
		{
			"doctype": "Skill Definition",
			"skill": skill,
			"description": spec["description"],
			"courses": [{"training_requirement": c} for c in courses],
			"roles": [{"training_role": spec["role"], "requirement_code": "R"}],
			"authorizer_role": spec.get("authorizer_role"),
		}
	)
	return True


def set_authorizer_roles() -> list[str]:
	"""Fill Also Authorized By on existing definitions where it is still blank (never overwritten)."""
	make_roles()
	updated = []
	for skill, spec in SKILLS.items():
		role = spec.get("authorizer_role")
		if role and frappe.db.exists("Skill Definition", skill):
			if not frappe.db.get_value("Skill Definition", skill, "authorizer_role"):
				frappe.db.set_value("Skill Definition", skill, "authorizer_role", role)
				updated.append(skill)
	return updated


def setup() -> list[str]:
	steps = [(c, create_course) for c in COURSES] + [(r, create_role) for r in ROLES]
	steps += [(s, create_skill) for s in SKILLS]
	created = [name for name, make in steps if make(name)]
	if created:
		enqueue_resync()
	return created
