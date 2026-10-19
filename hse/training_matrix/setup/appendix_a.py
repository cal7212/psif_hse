# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Training Roles and Training Requirements from TRN-700 Rev 1 Appendix A (TRN-701 Part 1).

Run from the "Load TRN-700 Appendix A" button on the Training Requirement list, or:
	bench --site <site> execute hse.training_matrix.setup.appendix_a.load_appendix_a

Existing records are left as they are, so edits made in Frappe are never overwritten.
Technical (TEC-) rows are illustrative in the SOP, so Managers add their own.
Two courses have no SAF number yet; they load as SAF-TBD-* and can be renamed.
"""

import frappe
from frappe import _

from hse.training_matrix.matrix import MANAGE_ROLES, enqueue_resync
from hse.training_matrix.status import ASSIGNED, HIRE, PER_CERTIFICATION

ROLES = ("Technician", "Logistics", "Customer Service", "Manager")

HR, SAFETY, QMS = "HR Onboarding", "Safety / EHS", "QMS"
ONCE, YEARLY, THREE_YEARS = "One-time", "Annually", "Every 3 Years"
R, C, NA = "R", "C", None  # NA: not required for the role

# (course_id, topic, avenue, delivery, verification, due basis, days, refresher,
#  retrain on revision, other triggers, minutes, high hazard, (Technician, Logistics, Customer Service, Manager))
# fmt: off
COURSES = [
	("HR-01", "New Hire Orientation (company overview, work rules, Employee Handbook)", HR, "Classroom",
	 "LMS Acknowledgment", HIRE, 0, ONCE, 0, None, None, 0, (R, R, R, R)),
	("HR-02", "Code of Conduct and Handbook Acknowledgment", HR, "Read & Acknowledge (LMS)",
	 "LMS Acknowledgment", HIRE, 0, ONCE, 1, None, None, 0, (R, R, R, R)),
	("HR-03", "Anti-Harassment, EEO, and Workplace Conduct", HR, "e-Learning",
	 "Quiz (80%)", HIRE, 30, YEARLY, 0, None, None, 0, (R, R, R, R)),
	("HR-04", "Timekeeping, Payroll, and Benefits Enrollment", HR, "Classroom",
	 "LMS Attendance Record", HIRE, 30, ONCE, 0, None, None, 0, (R, R, R, R)),
	("HR-05", "IT Systems, Cybersecurity, and Acceptable Use", HR, "e-Learning",
	 "Quiz (80%)", HIRE, 30, YEARLY, 0, None, None, 0, (R, R, R, R)),
	("HR-06", "Supervisor Responsibilities", HR, "Classroom",
	 "LMS Attendance Record", ASSIGNED, 90, ONCE, 0, "assigned on promotion", None, 0, (NA, NA, NA, R)),
	("SAF-TBD-ORIENT", "Safety Orientation (emergency action, fire prevention, injury reporting, stop-work authority)",
	 SAFETY, "Classroom", "Quiz (80%)", HIRE, 0, ONCE, 0, "before work", None, 0, (R, R, R, R)),
	("SAF-0002", "Forklift and Industrial Trucks", SAFETY, "Classroom / Practical",
	 "Practical Evaluation", ASSIGNED, 0, THREE_YEARS, 0, "before operation; evaluation per 29 CFR 1910.178",
	 None, 1, (R, R, NA, NA)),
	("SAF-0003", "Bloodborne Pathogens", SAFETY, None, "", ASSIGNED, 0, YEARLY, 0, None, None, 0, (R, NA, NA, NA)),
	("SAF-0004", "Disciplinary Program", SAFETY, "Classroom", "", HIRE, 0, YEARLY, 0, None, 15, 0, (R, R, R, R)),
	("SAF-0005", "Electrical Safety Awareness", SAFETY, "e-Learning", "", ASSIGNED, 0, YEARLY, 0, None, 22, 0,
	 (R, R, R, NA)),
	("SAF-TBD-70E", "Electrical Safety / NFPA 70E (Qualified Person)", SAFETY, "Classroom / OJT",
	 "Test and Practical", ASSIGNED, 0, YEARLY, 0, None, None, 1, (R, NA, NA, C)),
	("SAF-0006", "Fall Protection", SAFETY, "e-Learning", "Practical Demonstration", ASSIGNED, 0, YEARLY, 0, None,
	 45, 0, (R, R, NA, NA)),
	("SAF-0007", "Fire Protection", SAFETY, "e-Learning", "", ASSIGNED, 0, YEARLY, 0, None, 14, 0, (R, R, R, NA)),
	("SAF-0008", "First Aid / CPR / AED", SAFETY, "External", "Valid Certificate", ASSIGNED, 0, PER_CERTIFICATION,
	 0, "renew before expiration", None, 0, (R, NA, NA, NA)),
	("SAF-0009", "General Waste Management", SAFETY, "e-Learning", "", ASSIGNED, 0, YEARLY, 0, None, 30, 0,
	 (R, R, R, NA)),
	("SAF-0010", "Ground Fault Protection", SAFETY, "Classroom", "", ASSIGNED, 0, YEARLY, 0, None, 10, 0,
	 (R, R, NA, NA)),
	("SAF-0011", "Hand and Power Tools", SAFETY, "e-Learning", "", ASSIGNED, 0, YEARLY, 0, None, 15, 0,
	 (R, R, NA, NA)),
	("SAF-0012", "Hazard Communication (HazCom) / GHS and Safety Data Sheets", SAFETY, "e-Learning",
	 "Quiz (80%)", HIRE, 0, YEARLY, 0, "new chemical hazard", 26, 0, (R, R, R, R)),
	("SAF-0013", "Ladder Safety", SAFETY, "e-Learning", "Practical Demonstration", ASSIGNED, 0, YEARLY, 0, None,
	 14, 0, (R, R, R, NA)),
	("SAF-0014", "Noise Exposure / Hearing Conservation", SAFETY, "e-Learning", "LMS Completion Record",
	 ASSIGNED, 0, YEARLY, 0, None, 22, 0, (R, R, R, R)),
	("SAF-0015", "Non-DOT Drug and Alcohol Policy", SAFETY, "Classroom", "", HIRE, 0, YEARLY, 0, None, 15, 0,
	 (R, R, R, R)),
	("SAF-0016", "Personal Protective Equipment (PPE)", SAFETY, "e-Learning / Demonstration",
	 "Practical Demonstration", HIRE, 0, YEARLY, 0, None, 33, 0, (R, R, R, R)),
	("SAF-0017", "Respirator", SAFETY, None, "", ASSIGNED, 0, YEARLY, 0, None, None, 0, (R, NA, NA, NA)),
	("SAF-0018", "Risk Assessment", SAFETY, None, "", ASSIGNED, 0, YEARLY, 0, None, None, 0, (R, NA, NA, NA)),
	("SAF-0019", "Spill Prevention and Response", SAFETY, None, "Quiz (80%)", ASSIGNED, 0, YEARLY, 0, None, None,
	 0, (R, NA, NA, NA)),
	("SAF-0020", "Subcontractor Management", SAFETY, None, "", ASSIGNED, 0, YEARLY, 0, None, None, 0,
	 (NA, NA, NA, NA)),
	("SAF-0021", "Driver Safety", SAFETY, "e-Learning", "Quiz and MVR Review", ASSIGNED, 0, YEARLY, 0, None, 16, 0,
	 (R, R, R, R)),
	("SAF-0022", "Hydrogen Sulfide (H2S)", SAFETY, None, "", ASSIGNED, 0, YEARLY, 0, None, None, 0,
	 (R, NA, NA, NA)),
	("SAF-0023", "Forklift Safety Awareness", SAFETY, "e-Learning", "", HIRE, 0, YEARLY, 0, None, 18, 0,
	 (R, R, R, R)),
	("SAF-0024", "Lockout / Tagout (LOTO)", SAFETY, "Classroom / OJT", "Practical Demonstration", ASSIGNED, 0,
	 YEARLY, 0, None, None, 1, (R, NA, NA, NA)),
	("SAF-0026", "Safety Manual Overview", SAFETY, "Classroom", "", HIRE, 0, ONCE, 1, None, 15, 0, (R, R, R, R)),
	("QMS-01", "QMS Awareness (Quality Policy, objectives, employee contribution, nonconformity)", QMS,
	 "Classroom", "Quiz (80%)", HIRE, 90, ONCE, 0, "on significant change", None, 0, (R, R, R, R)),
	("QMS-02", "Document Control (QM-005)", QMS, "Read & Acknowledge", "LMS Acknowledgment", HIRE, 0, ONCE, 1,
	 None, None, 0, (R, R, R, R)),
	("QMS-03", "Nonconformance and Corrective Action", QMS, "Classroom", "Quiz (80%)", ASSIGNED, 0, ONCE, 0, None,
	 None, 0, (R, R, C, R)),
	("QMS-04", "Control of Records", QMS, "Read & Acknowledge", "LMS Acknowledgment", ASSIGNED, 0, ONCE, 1, None,
	 None, 0, (C, C, R, R)),
	("QMS-05", "Calibration and Control of Measuring Equipment", QMS, "OJT", "Practical Demonstration", ASSIGNED,
	 0, ONCE, 0, None, None, 0, (C, NA, NA, NA)),
	("QMS-06", "Internal Auditor", QMS, "External / Classroom", "Certificate and Observed Audit", ASSIGNED, 0,
	 ONCE, 0, "upon designation", None, 0, (NA, NA, NA, C)),
	("QMS-07", "Contract Review and Customer Requirements", QMS, "OJT", "Supervisor Observation", ASSIGNED, 0,
	 ONCE, 0, None, None, 0, (NA, NA, R, R)),
]
# fmt: on


def create_roles() -> list[str]:
	"""The four PSIF Training Roles, mapped to a Designation or Department of the same name if one exists."""
	created = []
	for role in ROLES:
		if frappe.db.exists("Training Role", role):
			continue
		doc = frappe.new_doc("Training Role")
		doc.role_name = role
		if frappe.db.exists("Designation", role):
			doc.append("designations", {"designation": role})
		if frappe.db.exists("Department", {"department_name": role}):
			for dept in frappe.get_all("Department", filters={"department_name": role}, pluck="name"):
				doc.append("departments", {"department": dept})
		doc.flags.skip_resync = True
		doc.insert(ignore_permissions=True)
		created.append(role)
	return created


def create_requirements() -> list[str]:
	created = []
	for (
		course_id,
		title,
		avenue,
		delivery,
		verification,
		basis,
		days,
		refresher,
		on_revision,
		notes,
		minutes,
		high_hazard,
		codes,
	) in COURSES:
		if frappe.db.exists("Training Requirement", course_id):
			continue
		doc = frappe.new_doc("Training Requirement")
		doc.update(
			{
				"course_id": course_id,
				"course_title": title,
				"avenue": avenue,
				"delivery_method": delivery,
				"verification_method": verification,
				"initial_due_basis": basis,
				"initial_due_days": days,
				"refresher_frequency": refresher,
				"retrain_on_revision": on_revision,
				"frequency_notes": notes,
				"duration_minutes": minutes,
				"high_hazard": high_hazard,
				"requires_qualified_trainer": high_hazard,
				"all_employees": 1 if all(c == R for c in codes) else 0,
			}
		)
		for role, code in zip(ROLES, codes, strict=True):
			if code:
				doc.append("roles", {"training_role": role, "requirement_code": code})
		doc.flags.skip_resync = True
		doc.insert(ignore_permissions=True)
		created.append(course_id)
	return created


@frappe.whitelist()
def load_appendix_a() -> dict:
	frappe.only_for(MANAGE_ROLES)
	roles = create_roles()
	courses = create_requirements()
	if roles or courses:
		enqueue_resync()
	frappe.msgprint(
		_(
			"Created {0} Training Roles and {1} Training Requirements. Existing records were left unchanged."
		).format(len(roles), len(courses))
	)
	return {"roles": roles, "requirements": courses}
