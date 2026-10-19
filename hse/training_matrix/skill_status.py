# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Skill status rules (Phase 2b), kept free of database calls.

A skill (a Frappe HR Skill with a Skill Definition) is a broader competency made of courses and,
optionally, prerequisite skills. Being Qualified in all of them makes the employee *eligible*;
only a manager's Skill Authorization *grants* the skill.

- eligible_since: the date the employee last became eligible. It resets whenever eligibility is
  lost, so an authorization given before a lapse no longer counts: the skill needs a new
  authorization once the courses are current again.
- A prerequisite counts only while it is Authorized, so losing a lower rung removes every skill
  built on it.
"""

from frappe.utils import getdate

NOT_STARTED = "Not Started"
IN_TRAINING = "In Training"
READY = "Ready for Authorization"
AUTHORIZED = "Authorized"
LAPSED = "Lapsed"
STATUSES = (NOT_STARTED, IN_TRAINING, READY, AUTHORIZED, LAPSED)


def dependency_order(definitions: dict, skills) -> list[str]:
	"""Skills with their prerequisites first (prerequisites added if missing)."""
	order, seen = [], set()

	def visit(skill, path=()):
		if skill in seen:
			return
		if skill in path:
			raise ValueError(f"Circular skill prerequisites: {' → '.join((*path, skill))}")
		for prereq in (definitions.get(skill) or {}).get("prerequisites", ()):
			visit(prereq, (*path, skill))
		seen.add(skill)
		order.append(skill)

	for skill in sorted(skills):
		visit(skill)
	return order


def evaluate(
	definitions: dict,
	skills,
	qualified: set,
	started: set,
	state: dict,
	authorizations: dict,
	on_date,
) -> dict:
	"""Status of each skill for one employee.

	definitions: {skill: {"courses": [...], "prerequisites": [...]}}
	skills: skills to evaluate (prerequisites are added automatically)
	qualified: courses the employee is currently Qualified in
	started: courses with any progress (in progress or previously completed)
	state: {skill: {"eligible_since": date}} as stored on the matrix
	authorizations: {skill: [{"name", "date", "expires_on"}, ...]} submitted, not cancelled
	"""
	on_date = getdate(on_date)
	results: dict[str, dict] = {}
	for skill in dependency_order(definitions, skills):
		d = definitions.get(skill) or {"courses": [], "prerequisites": []}
		missing = [c for c in d["courses"] if c not in qualified]
		missing_prereqs = [p for p in d["prerequisites"] if results.get(p, {}).get("status") != AUTHORIZED]
		eligible = not missing and not missing_prereqs
		since = (state.get(skill) or {}).get("eligible_since") if eligible else None
		since = getdate(since) if since else (on_date if eligible else None)

		auths = sorted(authorizations.get(skill, []), key=lambda a: getdate(a["date"]))
		valid = [
			a
			for a in auths
			if eligible
			and getdate(a["date"]) >= since
			and (not a.get("expires_on") or getdate(a["expires_on"]) >= on_date)
		]
		if valid:
			status = AUTHORIZED
		elif eligible:
			status = READY
		elif auths:
			status = LAPSED
		elif any(c in qualified or c in started for c in d["courses"]):
			status = IN_TRAINING
		else:
			status = NOT_STARTED
		latest = valid[-1] if valid else None
		results[skill] = {
			"status": status,
			"eligible_since": since,
			"skill_authorization": latest["name"] if latest else None,
			"authorized_on": getdate(latest["date"]) if latest else None,
			"authorization_expires": getdate(latest["expires_on"])
			if latest and latest.get("expires_on")
			else None,
			"courses_required": len(d["courses"]),
			"courses_qualified": len(d["courses"]) - len(missing),
			"missing": ", ".join(missing + [f"{p} (skill)" for p in missing_prereqs]),
		}
	return results


def skill_courses(definitions: dict, skill: str) -> list[str]:
	"""Every course a skill needs, including its prerequisites' courses."""
	courses = []
	for s in dependency_order(definitions, [skill]):
		for c in (definitions.get(s) or {}).get("courses", ()):
			if c not in courses:
				courses.append(c)
	return courses
