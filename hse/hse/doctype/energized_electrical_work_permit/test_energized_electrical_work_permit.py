# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import add_to_date, now_datetime

from hse.hse.doctype.energized_electrical_work_permit.energized_electrical_work_permit import approval_errors
from hse.hse.permits import close_permit
from hse.testing_fixtures import ensure_company, ensure_employee

EEWP = "Energized Electrical Work Permit"


def complete(**kw):
	start = now_datetime()
	values = {
		"equipment_description": "_Test MCC-2 bucket 4B",
		"work_description": "Replace contactor coil",
		"work_start": start,
		"work_end": add_to_date(start, hours=2),
		"justification_type": "Infeasibility",
		"justification": "Continuous cure oven cannot be shut down",
		"esc_not_feasible": 1,
		"nominal_voltage": "480 V",
		"limited_approach": "3 ft 6 in",
		"restricted_approach": "1 ft 0 in",
		"shock_ppe": "Class 0 gloves",
		"arc_method": "Incident Energy Analysis",
		"incident_energy": 6.2,
		"working_distance": "18 in",
		"arc_flash_boundary": "4 ft",
		"arc_flash_ppe": "8 cal AR clothing",
		"safe_work_practices": "Test before touch",
		"acc_barricade": 1,
		"briefing_done": 1,
		"workers": [{"worker_name": "_Test Electrician", "role": "Qualified Person", "briefed": 1}],
	}
	values.update(kw)
	doc = frappe.new_doc(EEWP)
	doc.update(values)
	return doc


class UnitTestEnergizedElectricalWorkPermit(UnitTestCase):
	def test_complete_permit_has_no_errors(self):
		self.assertEqual(approval_errors(complete()), [])

	def test_missing_elements(self):
		self.assertEqual(len(approval_errors(complete(justification="", shock_ppe=None))), 2)
		self.assertEqual(len(approval_errors(complete(esc_not_feasible=0))), 1)

	def test_arc_flash(self):
		self.assertTrue(any("40" in e for e in approval_errors(complete(incident_energy=45))))
		self.assertEqual(len(approval_errors(complete(arc_method="PPE Category Method"))), 1)
		self.assertEqual(approval_errors(complete(arc_method="PPE Category Method", ppe_category="2")), [])

	def test_workers_and_briefing(self):
		errors = approval_errors(complete(briefing_done=0, workers=[{"worker_name": "X", "role": "Worker"}]))
		self.assertEqual(len(errors), 3)  # no qualified person, no briefing, X not briefed


class IntegrationTestEnergizedElectricalWorkPermit(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = ensure_company()
		cls.requester = ensure_employee("_Test EEWP Requester", cls.company)

	def test_approve_and_close(self):
		doc = complete(company=self.company, requested_by=self.requester)
		doc.insert()
		self.assertEqual(doc.status, "Draft")
		doc.submit()
		self.assertEqual((doc.status, doc.approved_by), ("Approved", frappe.session.user))
		close_permit(EEWP, doc.name, "Work Completed", "Coil replaced")
		doc.reload()
		self.assertEqual(doc.status, "Closed")
