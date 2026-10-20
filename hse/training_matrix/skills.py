# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Skills (Phase 2b): broader competencies built from courses, granted by a manager.

- A Skill Definition says which courses and prerequisite skills a Frappe HR Skill needs, and
  which Training Roles need it (R / C). Its courses flow onto those employees' matrices.
- A manager can set target skills on an employee (development). Their courses are added as
  development training (Dev), tracked but outside TRN-700 compliance.
- Being Qualified in every course makes the employee eligible; the manager's Skill
  Authorization grants the skill. The Frappe HR Employee Skill Map mirrors the result: granted
  skills at their proficiency, skills still needed at zero. Only skills with a Skill Definition
  are managed here; other skills on the HR skill map are left alone.
- Designations get the skills their Training Role requires, so HR shows the right skills for
  each job.
"""

import frappe
from frappe import _
from frappe.utils import add_months, getdate, today

from hse.training_matrix import skill_status as ss
from hse.training_matrix import status as st

SKILL_DEF = "Skill Definition"
MANAGE_ROLES = ("System Manager", "HR Manager", "Training Coordinator")
CODE_RANK = {st.REQUIRED: 3, st.CONDITIONAL: 2, st.DEVELOPMENT: 1}


# ---------------------------------------------------------------- definitions
def definitions() -> dict[str, dict]:
	defs = {
		d.name: {
			"courses": [],
			"prerequisites": [],
			"proficiency": d.proficiency,
			"months": d.authorization_valid_months,
		}
		for d in frappe.get_all(
			SKILL_DEF, filters={"disabled": 0}, fields=["name", "proficiency", "authorization_valid_months"]
		)
	}
	if not defs:
		return {}
	for r in frappe.get_all(
		"Skill Definition Course",
		filters={"parenttype": SKILL_DEF, "parent": ["in", list(defs)]},
		fields=["parent", "training_requirement"],
		order_by="idx asc",
	):
		defs[r.parent]["courses"].append(r.training_requirement)
	for r in frappe.get_all(
		"Skill Definition Prerequisite",
		filters={"parenttype": SKILL_DEF, "parent": ["in", list(defs)]},
		fields=["parent", "skill"],
	):
		defs[r.parent]["prerequisites"].append(r.skill)
	return defs


def role_skills(roles: list[str]) -> dict[str, str]:
	"""{skill: 'R' | 'C'} needed by the Training Roles (stricter code wins)."""
	codes: dict[str, str] = {}
	if not roles:
		return codes
	enabled = set(frappe.get_all(SKILL_DEF, filters={"disabled": 0}, pluck="name"))
	for r in frappe.get_all(
		"Skill Definition Role",
		filters={"parenttype": SKILL_DEF, "training_role": ["in", roles]},
		fields=["parent", "requirement_code"],
	):
		if r.parent in enabled and CODE_RANK[r.requirement_code] > CODE_RANK.get(codes.get(r.parent), 0):
			codes[r.parent] = r.requirement_code
	return codes


def merge_skill_courses(codes: dict, needed_for: dict, roles, targets, defs) -> tuple[dict, dict]:
	"""Add the courses of role skills (R / C) and target skills (Dev) to the course codes.

	codes / needed_for are updated in place; returns (skill_needed_for, development_due).
	"""
	skill_needed_for: dict[str, str] = {}
	development_due: dict[str, object] = {}

	def add(course, code, label):
		if CODE_RANK[code] > CODE_RANK.get(codes.get(course), 0):
			codes[course] = code
		needed_for.setdefault(course, set()).add(label)

	for skill, code in role_skills(roles).items():
		for s in ss.dependency_order(defs, [skill]):
			skill_needed_for.setdefault(s, "Role" if s == skill else "Prerequisite")
		for course in ss.skill_courses(defs, skill):
			add(course, code, skill)

	for target in targets:
		if target.skill not in defs:
			continue
		for s in ss.dependency_order(defs, [target.skill]):
			skill_needed_for.setdefault(s, "Target" if s == target.skill else "Prerequisite")
		for course in ss.skill_courses(defs, target.skill):
			add(course, st.DEVELOPMENT, target.skill)
			if codes[course] == st.DEVELOPMENT:
				due = getdate(target.due_date) if target.due_date else None
				if due and (course not in development_due or due < development_due[course]):
					development_due[course] = due
	return skill_needed_for, development_due


def authorizations(employee: str) -> dict[str, list[dict]]:
	out: dict[str, list[dict]] = {}
	for a in frappe.get_all(
		"Skill Authorization",
		filters={"employee": employee, "docstatus": 1},
		fields=["name", "skill", "authorization_date", "expires_on"],
	):
		out.setdefault(a.skill, []).append(
			{"name": a.name, "date": a.authorization_date, "expires_on": a.expires_on}
		)
	return out


# ---------------------------------------------------------------- matrix
def set_skill_rows(matrix, skill_needed_for: dict[str, str], defs: dict) -> None:
	"""Keep a skill row for every skill needed (role, target, prerequisite) or still held."""
	held = {s for s, auths in authorizations(matrix.employee).items() if auths and s in defs}
	wanted = dict(skill_needed_for)
	for s in held:
		wanted.setdefault(s, "Held")
	existing = {r.skill: r for r in matrix.skills}
	matrix.set("skills", [])
	for skill in ss.dependency_order(defs, [s for s in wanted if s in defs]):
		row = existing.get(skill)
		data = row.as_dict() if row else {"skill": skill}
		data["needed_for"] = wanted.get(skill, "Prerequisite")
		for key in ("name", "idx", "parent", "parentfield", "parenttype", "doctype"):
			data.pop(key, None)
		matrix.append("skills", data)
	targets = {t.skill: t.due_date for t in matrix.target_skills}
	for row in matrix.skills:
		row.target_due = targets.get(row.skill)


def apply_skills(matrix, on_date=None, defs=None) -> list[str]:
	"""Recalculate every skill row; returns skills that just became Ready for Authorization."""
	if not matrix.get("skills"):
		return []
	defs = defs if defs is not None else definitions()
	qualified = {r.training_requirement for r in matrix.items if r.qualification == st.QUALIFIED}
	started = {r.training_requirement for r in matrix.items if r.in_progress or r.completed_on}
	state = {r.skill: {"eligible_since": r.eligible_since} for r in matrix.skills}
	before = {r.skill: r.status for r in matrix.skills}
	results = ss.evaluate(
		defs,
		[r.skill for r in matrix.skills if r.skill in defs],
		qualified,
		started,
		state,
		authorizations(matrix.employee),
		on_date or today(),
	)
	newly_ready = []
	for row in matrix.skills:
		res = results.get(row.skill)
		if not res:
			continue
		row.update(res)
		row.progress = f"{res['courses_qualified']}/{res['courses_required']}"
		if res["status"] == ss.READY and before.get(row.skill) != ss.READY:
			newly_ready.append(row.skill)
	return newly_ready


def after_matrix_update(matrix) -> None:
	"""On save: tell managers about skills ready for authorization; mirror the HR skill map."""
	for skill in matrix.flags.get("ready_skills") or []:
		notify_ready(matrix, skill)
	sync_hr_skill_map(matrix)


def notify_ready(matrix, skill: str) -> None:
	from frappe.desk.form.assign_to import add as assign

	users = manager_users(matrix.employee)
	if not users:
		return
	try:
		assign(
			{
				"assign_to": users,
				"doctype": matrix.doctype,
				"name": matrix.name,
				"description": _(
					"{0} is ready for authorization as {1}. Review and submit a Skill Authorization."
				).format(matrix.employee_name, skill),
			}
		)
	except Exception:
		pass  # already assigned


def manager_users(employee: str) -> list[str]:
	manager = frappe.db.get_value("Employee", employee, "reports_to")
	user = frappe.db.get_value("Employee", manager, "user_id") if manager else None
	if user:
		return [user]
	return sorted(
		{
			u
			for u in frappe.get_all(
				"Has Role", filters={"role": "HR Manager", "parenttype": "User"}, pluck="parent"
			)
			if u not in ("Administrator", "Guest") and frappe.db.get_value("User", u, "enabled")
		}
	)


# ---------------------------------------------------------------- Frappe HR mirrors
def hrms_ready() -> bool:
	return bool(frappe.db.exists("DocType", "Employee Skill Map"))


def sync_hr_skill_map(matrix) -> None:
	"""Employee Skill Map: authorized skills at their proficiency, needed skills at zero."""
	if not hrms_ready() or (
		not matrix.get("skills") and not frappe.db.exists("Employee Skill Map", matrix.employee)
	):
		return
	managed = set(frappe.get_all(SKILL_DEF, pluck="name"))
	proficiency = {d.name: d.proficiency for d in frappe.get_all(SKILL_DEF, fields=["name", "proficiency"])}
	desired = {}
	for row in matrix.skills:
		if row.status == ss.AUTHORIZED:
			desired[row.skill] = (proficiency.get(row.skill) or 1, row.authorized_on)
		elif row.needed_for != "Held" and matrix.active:
			desired[row.skill] = (0, None)

	if frappe.db.exists("Employee Skill Map", matrix.employee):
		doc = frappe.get_doc("Employee Skill Map", matrix.employee)
	else:
		if not desired:
			return
		doc = frappe.new_doc("Employee Skill Map")
		doc.employee = matrix.employee

	current = {r.skill: r for r in doc.employee_skills}
	changed = False
	for row in list(doc.employee_skills):
		if row.skill in managed and row.skill not in desired:
			doc.remove(row)
			changed = True
	for skill, (prof, on) in desired.items():
		row = current.get(skill)
		if not row:
			doc.append("employee_skills", {"skill": skill, "proficiency": prof, "evaluation_date": on})
			changed = True
		elif (float(row.proficiency or 0), str(row.evaluation_date or "")) != (float(prof), str(on or "")):
			row.proficiency, row.evaluation_date = prof, on
			changed = True
	if changed or doc.is_new():
		doc.flags.ignore_permissions = True
		doc.save()


def sync_designation_skills() -> None:
	"""Each Designation lists the skills its Training Roles require (R)."""
	if not frappe.get_meta("Designation").has_field("skills"):
		return
	managed = set(frappe.get_all(SKILL_DEF, pluck="name"))
	required: dict[str, set] = {}
	for role in frappe.get_all("Training Role", filters={"disabled": 0}, pluck="name"):
		skills = {s for s, code in role_skills([role]).items() if code == st.REQUIRED}
		for d in frappe.get_all(
			"Training Role Designation",
			filters={"parent": role, "parenttype": "Training Role"},
			pluck="designation",
		):
			required.setdefault(d, set()).update(skills)
	for designation in frappe.get_all("Designation", pluck="name"):
		doc = frappe.get_doc("Designation", designation)
		want = required.get(designation, set())
		have = {r.skill for r in doc.skills}
		keep = [r for r in doc.skills if r.skill not in managed or r.skill in want]
		if len(keep) == len(doc.skills) and want <= have:
			continue
		doc.set("skills", [r.as_dict() for r in keep])
		for skill in sorted(want - have):
			doc.append("skills", {"skill": skill})
		doc.flags.ignore_permissions = True
		doc.save()


# ---------------------------------------------------------------- manager actions
def is_manager_of(employee: str, user: str | None = None) -> bool:
	user = user or frappe.session.user
	if set(frappe.get_roles(user)) & set(MANAGE_ROLES):
		return True
	manager = frappe.db.get_value("Employee", employee, "reports_to")
	return bool(manager and frappe.db.get_value("Employee", manager, "user_id") == user)


def _check_manager(employee: str) -> None:
	if not is_manager_of(employee):
		frappe.throw(
			_("Only the employee's manager, HR or the Training Coordinator can do this."),
			frappe.PermissionError,
		)


@frappe.whitelist()
def set_target_skill(employee: str, skill: str, due_date: str, notes: str | None = None) -> None:
	_check_manager(employee)
	if not frappe.db.exists(SKILL_DEF, {"name": skill, "disabled": 0}):
		frappe.throw(_("{0} has no Skill Definition yet.").format(frappe.bold(skill)))
	from hse.training_matrix.matrix import sync_matrix

	matrix = frappe.get_doc("Employee Training Matrix", employee)
	row = next((t for t in matrix.target_skills if t.skill == skill), None)
	if row:
		row.due_date, row.notes = due_date, notes
	else:
		matrix.append(
			"target_skills",
			{"skill": skill, "due_date": due_date, "notes": notes, "set_by": frappe.session.user},
		)
	matrix.flags.ignore_permissions = True
	matrix.save()
	sync_matrix(employee)


@frappe.whitelist()
def remove_target_skill(employee: str, skill: str) -> None:
	_check_manager(employee)
	from hse.training_matrix.matrix import sync_matrix

	matrix = frappe.get_doc("Employee Training Matrix", employee)
	matrix.set("target_skills", [t for t in matrix.target_skills if t.skill != skill])
	matrix.flags.ignore_permissions = True
	matrix.save()
	sync_matrix(employee)


@frappe.whitelist()
def set_applicability(employee: str, training_requirement: str, applicability: str) -> None:
	"""The manager confirms whether a conditional (C) course applies to the employee."""
	_check_manager(employee)
	if applicability not in (st.APPLIES, st.DOES_NOT_APPLY):
		frappe.throw(_("Applicability must be Applies or Not Applicable."))
	matrix = frappe.get_doc("Employee Training Matrix", employee)
	row = next((r for r in matrix.items if r.training_requirement == training_requirement), None)
	if not row or row.requirement_code != st.CONDITIONAL:
		frappe.throw(_("{0} is not a conditional course on this matrix.").format(training_requirement))
	row.applicability = applicability
	matrix.flags.ignore_permissions = True
	matrix.save()


def authorization_expiry(skill: str, authorization_date) -> str | None:
	months = frappe.db.get_value(SKILL_DEF, skill, "authorization_valid_months")
	return add_months(authorization_date, months) if months else None
