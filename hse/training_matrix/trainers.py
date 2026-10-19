# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Qualified Trainer register (TRN-700 Rev 1 §4.8).

A trainer is authorized for a course when the register lists it as Active. A course is suspended
while the trainer's certification is expired or the trainer is no longer Qualified in it.
"""

import frappe
from frappe import _
from frappe.utils import getdate, today

from hse.training_matrix import status as st

ROLE = "Qualified Trainer"


def is_authorized(employee: str | None, requirement: str) -> bool:
	if not employee:
		return False
	if frappe.db.get_value("Qualified Trainer", employee, "disabled") in (None, 1):
		return False
	return bool(
		frappe.db.exists(
			"Qualified Trainer Course",
			{
				"parent": employee,
				"parenttype": "Qualified Trainer",
				"training_requirement": requirement,
				"status": "Active",
			},
		)
	)


def check_authorized(employee: str | None, requirement: str, label: str) -> None:
	if not is_authorized(employee, requirement):
		frappe.throw(
			_(
				"{0} must be a Qualified Trainer for {1} (TRN-700 §4.8). Check the Qualified Trainer register."
			).format(label, frappe.bold(requirement)),
			title=_("Not a Qualified Trainer"),
		)


def own_qualification(employee: str) -> dict[str, str]:
	"""{course: qualification} from the trainer's own matrix."""
	return {
		r.training_requirement: r.qualification
		for r in frappe.get_all(
			"Employee Training Matrix Item",
			filters={"parent": employee, "parenttype": "Employee Training Matrix"},
			fields=["training_requirement", "qualification"],
		)
	}


def suspension_reason(row, qualified: dict[str, str], on_date) -> str | None:
	if row.certification_expires and getdate(row.certification_expires) < getdate(on_date):
		return _("Trainer certification expired {0}").format(frappe.format(row.certification_expires, "Date"))
	if qualified.get(row.training_requirement) != st.QUALIFIED:
		return _("Trainer is not currently Qualified in this course")
	return None


def sync_role(user: str | None, active: bool) -> None:
	"""Give the trainer's login the Qualified Trainer role while they have an active course."""
	if not user or not frappe.db.exists("User", user):
		return
	has = frappe.db.exists("Has Role", {"parent": user, "parenttype": "User", "role": ROLE})
	if active and not has:
		frappe.get_doc("User", user).add_roles(ROLE)
	elif not active and has:
		frappe.get_doc("User", user).remove_roles(ROLE)


def refresh_register(on_date=None) -> None:
	"""Daily: suspend or restore courses as certifications expire or qualifications lapse."""
	on_date = on_date or today()
	for name in frappe.get_all("Qualified Trainer", filters={"disabled": 0}, pluck="name"):
		doc = frappe.get_doc("Qualified Trainer", name)
		before = [(r.status, r.suspension_reason) for r in doc.courses]
		doc.apply_status(on_date)
		if before != [(r.status, r.suspension_reason) for r in doc.courses]:
			doc.flags.ignore_permissions = True
			doc.flags.from_refresh = True
			doc.save()
