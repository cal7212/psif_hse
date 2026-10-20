# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Builds and refreshes the TRN-701 Employee Training Matrix (TRN-700 Rev 1 §4.9).

Each active Employee has one Employee Training Matrix. Its Training Roles come from the
employee's Designation or Department (Training Role mapping) unless the Training Coordinator
sets them by hand. Its rows are every Training Requirement marked All Employees or marked R / C
for one of those roles. Rows with recorded training are kept when a requirement stops applying,
so the history survives a job change.
"""

import copy

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime, today

from hse.training_matrix import skills as sk
from hse.training_matrix import status as st

MATRIX = "Employee Training Matrix"
ITEM = "Employee Training Matrix Item"
MANAGE_ROLES = ("System Manager", "HR Manager", "Training Coordinator")

# Requirement fields the status rules and the denormalized row columns need.
REQ_FIELDS = (
	"name",
	"course_title",
	"avenue",
	"high_hazard",
	"initial_due_basis",
	"initial_due_days",
	"refresher_frequency",
)
# Employee fields copied onto the matrix and its rows (for reports and Insights).
EMP_FIELDS = (
	"name",
	"employee_name",
	"user_id",
	"department",
	"designation",
	"company",
	"date_of_joining",
	"status",
)


# ---------------------------------------------------------------- lookups
def roles_for_employee(
	designation: str | None, department: str | None, employee: str | None = None
) -> list[str]:
	"""Enabled Training Roles mapped to the employee's Designation, Department or Employee Groups."""
	roles = set()
	if employee:
		groups = frappe.get_all(
			"Employee Group Table",
			filters={"employee": employee, "parenttype": "Employee Group"},
			pluck="parent",
		)
		if groups:
			roles.update(
				frappe.get_all(
					"Training Role Employee Group",
					filters={"employee_group": ["in", groups], "parenttype": "Training Role"},
					pluck="parent",
				)
			)
	if designation:
		roles.update(
			frappe.get_all(
				"Training Role Designation",
				filters={"designation": designation, "parenttype": "Training Role"},
				pluck="parent",
			)
		)
	if department:
		roles.update(
			frappe.get_all(
				"Training Role Department",
				filters={"department": department, "parenttype": "Training Role"},
				pluck="parent",
			)
		)
	if not roles:
		return []
	return sorted(
		frappe.get_all("Training Role", filters={"name": ["in", list(roles)], "disabled": 0}, pluck="name")
	)


def requirement_codes(roles: list[str]) -> dict[str, str]:
	"""{requirement: 'R' | 'C'} for the given Training Roles, plus All Employees courses.
	When roles disagree the stricter code wins (R over C)."""
	enabled = set(frappe.get_all("Training Requirement", filters={"disabled": 0}, pluck="name"))
	codes = {
		name: st.REQUIRED
		for name in frappe.get_all(
			"Training Requirement", filters={"disabled": 0, "all_employees": 1}, pluck="name"
		)
	}
	if roles:
		for row in frappe.get_all(
			"Training Requirement Role",
			filters={"training_role": ["in", roles], "parenttype": "Training Requirement"},
			fields=["parent", "requirement_code"],
		):
			if row.parent not in enabled:
				continue
			if codes.get(row.parent) != st.REQUIRED:
				codes[row.parent] = row.requirement_code
	return codes


def requirement_map(names) -> dict[str, frappe._dict]:
	if not names:
		return {}
	return {
		r.name: r
		for r in frappe.get_all(
			"Training Requirement", filters={"name": ["in", list(names)]}, fields=REQ_FIELDS
		)
	}


# ---------------------------------------------------------------- refresh
def apply_status(matrix, requirements: dict | None = None, on_date=None):
	"""Recalculate every row and the summary on an in-memory matrix document."""
	on_date = getdate(on_date or today())
	requirements = requirements or requirement_map({r.training_requirement for r in matrix.items})
	for row in matrix.items:
		req = requirements.get(row.training_requirement) or {}
		if row.requirement_code != st.CONDITIONAL:
			row.applicability = None
		if row.completed_on and not row.first_completed_on:
			row.first_completed_on = row.completed_on
		row.update(st.evaluate(row.as_dict(), req, matrix.date_of_joining, on_date))
		row.update(
			{
				"course_title": req.get("course_title"),
				"avenue": req.get("avenue"),
				"high_hazard": req.get("high_hazard") or 0,
				"employee": matrix.employee,
				"employee_name": matrix.employee_name,
				"department": matrix.department,
				"company": matrix.company,
				"active": matrix.active,
			}
		)
	matrix.flags.ready_skills = sk.apply_skills(matrix, on_date)
	update_summary(matrix)


def update_summary(matrix):
	rows = [r.as_dict() for r in matrix.items]
	required = [r for r in rows if r.is_required]
	matrix.required_count = len(required)
	matrix.compliant_count = sum(1 for r in required if r.qualification == st.QUALIFIED)
	matrix.overdue_count = sum(1 for r in required if r.status == st.OVERDUE)
	matrix.due_count = sum(1 for r in required if r.status == st.DUE)
	matrix.confirm_count = sum(1 for r in rows if r.status == st.CONFIRM)
	matrix.percent_complete = st.percent_complete(rows)
	matrix.no_lms_login = 0 if matrix.user_id else 1
	matrix.last_refreshed = now_datetime()


def sync_matrix(employee: str, on_date=None):
	"""Create or update one employee's matrix from HR data and the current requirements."""
	emp = frappe.db.get_value("Employee", employee, EMP_FIELDS, as_dict=True)
	if not emp:
		return None
	on_date = getdate(on_date or today())
	if frappe.db.exists(MATRIX, employee):
		matrix = frappe.get_doc(MATRIX, employee)
	else:
		if emp.status != "Active":
			return None
		matrix = frappe.new_doc(MATRIX)
		matrix.employee = employee
		matrix.roles_from_hr = 1

	matrix.update(
		{
			"employee_name": emp.employee_name,
			"user_id": emp.user_id,
			"department": emp.department,
			"designation": emp.designation,
			"company": emp.company,
			"date_of_joining": emp.date_of_joining,
			"active": 1 if emp.status == "Active" else 0,
		}
	)
	if matrix.roles_from_hr:
		matrix.set(
			"roles",
			[{"training_role": r} for r in roles_for_employee(emp.designation, emp.department, employee)],
		)

	if matrix.active:
		roles = [r.training_role for r in matrix.roles]
		codes = requirement_codes(roles)
		needed_for = {course: {"Role"} for course in codes}
		defs = sk.definitions()
		skill_needed_for, development_due = sk.merge_skill_courses(
			codes, needed_for, roles, matrix.target_skills, defs
		)
		reconcile_rows(matrix, codes, on_date, needed_for, development_due)
		sk.set_skill_rows(matrix, skill_needed_for, defs)
	matrix.flags.ignore_permissions = True
	matrix.flags.on_date = on_date
	matrix.save()
	return matrix


def reconcile_rows(matrix, codes: dict[str, str], on_date, needed_for=None, development_due=None):
	"""Add newly required courses, update codes, drop rows that no longer apply and have no history."""
	existing = {}
	for row in list(matrix.items):
		if row.training_requirement in existing:  # duplicate row: keep the one with history
			keep = existing[row.training_requirement]
			if row.completed_on and not keep.completed_on:
				matrix.remove(keep)
				existing[row.training_requirement] = row
			else:
				matrix.remove(row)
			continue
		existing[row.training_requirement] = row

	for name, row in existing.items():
		code = codes.get(name)
		if code:
			if row.requirement_code != code:
				# a course that stopped applying and now applies again is newly assigned
				if not row.assigned_on or row.requirement_code == st.NOT_REQUIRED:
					row.assigned_on = on_date
				row.requirement_code = code
		elif row.completed_on or row.in_progress:
			row.requirement_code = st.NOT_REQUIRED
		else:
			matrix.remove(row)

	for name, code in sorted(codes.items()):
		if name not in existing:
			matrix.append(
				"items", {"training_requirement": name, "requirement_code": code, "assigned_on": on_date}
			)

	needed_for, development_due = needed_for or {}, development_due or {}
	for row in matrix.items:
		labels = sorted(needed_for.get(row.training_requirement) or ())
		row.needed_for = ", ".join(labels) if labels else None
		row.development_due = development_due.get(row.training_requirement)

	matrix.items.sort(key=lambda r: r.training_requirement)
	for i, row in enumerate(matrix.items, 1):
		row.idx = i


def _fingerprint(matrix):
	return (
		[(r.name, r.status, r.qualification, str(r.due_date or "")) for r in matrix.items],
		[(r.skill, r.status, str(r.eligible_since or ""), r.skill_authorization) for r in matrix.skills],
	)


def refresh_matrix_status(name: str, on_date=None) -> bool:
	"""Daily job: recalculate statuses. Saves (with a Version) only when a status changed, so
	skill notifications and the HR skill map follow; otherwise just stamps last_refreshed."""
	matrix = frappe.get_doc(MATRIX, name)
	probe = copy.deepcopy(matrix)  # recalculate on a copy so save() still sees the transitions
	apply_status(probe, on_date=on_date)
	if _fingerprint(probe) == _fingerprint(matrix):
		matrix.db_set("last_refreshed", now_datetime(), update_modified=False)
		return False
	matrix.flags.ignore_permissions = True
	matrix.flags.on_date = on_date
	matrix.save()
	return True


# ---------------------------------------------------------------- bulk
def resync_all():
	"""Re-sync every active employee (after a Training Requirement, Training Role or Skill
	Definition change), and the skills each Designation lists in Frappe HR."""
	try:
		sk.sync_designation_skills()
	except Exception:
		frappe.log_error(title=_("Designation skills sync failed"))
	for employee in frappe.get_all("Employee", filters={"status": "Active"}, pluck="name"):
		try:
			sync_matrix(employee)
		except Exception:
			frappe.log_error(title=_("Training matrix sync failed for {0}").format(employee))


def enqueue_resync():
	frappe.enqueue(
		"hse.training_matrix.matrix.resync_all",
		queue="long",
		job_id="hse_training_matrix_resync",
		deduplicate=True,
		enqueue_after_commit=True,
	)


# ---------------------------------------------------------------- desk actions
@frappe.whitelist()
def sync_employee_matrix(employee: str) -> str | None:
	"""'Sync from HR' button on the matrix and the Employee form."""
	frappe.only_for(MANAGE_ROLES)
	matrix = sync_matrix(employee)
	return matrix.name if matrix else None


@frappe.whitelist()
def resync_all_matrices() -> None:
	"""'Re-sync all employees' button on the Training Requirement and Training Role lists."""
	frappe.only_for(MANAGE_ROLES)
	enqueue_resync()
	frappe.msgprint(_("Every active employee's training matrix will be re-synced in the background."))
