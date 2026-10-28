# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt

from datetime import date, timedelta

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils import now_datetime

from hse.quality_metrics.metrics import (
	AT_LEAST,
	AT_MOST,
	FAILED,
	OPEN,
	PASSED,
	RECORD_ONLY,
	calculate,
	evaluate,
	get_review_period,
	target_text,
)
from hse.testing_fixtures import ensure_company, ensure_gender

PROC = "_Test Quality Metrics Procedure"
GOAL = "_Test NC Metrics Goal"


class UnitTestQualityMetrics(UnitTestCase):
	def test_monthly_period_is_previous_month(self):
		self.assertEqual(get_review_period("Monthly", "2026-10-01"), (date(2026, 9, 1), date(2026, 9, 30)))
		self.assertEqual(get_review_period(None, "2026-03-15"), (date(2026, 2, 1), date(2026, 2, 28)))

	def test_weekly_period_is_previous_mon_to_sun(self):
		# 2026-10-01 is a Thursday
		self.assertEqual(get_review_period("Weekly", "2026-10-01"), (date(2026, 9, 21), date(2026, 9, 27)))

	def test_quarterly_and_daily(self):
		self.assertEqual(get_review_period("Quarterly", "2026-10-01"), (date(2026, 7, 1), date(2026, 9, 30)))
		self.assertEqual(get_review_period("Daily", "2026-10-01"), (date(2026, 9, 30), date(2026, 9, 30)))

	def test_evaluate(self):
		self.assertEqual(evaluate(92, AT_LEAST, 90), PASSED)
		self.assertEqual(evaluate(88, AT_LEAST, 90), FAILED)
		self.assertEqual(evaluate(0, AT_MOST, 0), PASSED)
		self.assertEqual(evaluate(1, AT_MOST, 0), FAILED)
		self.assertEqual(evaluate(None, AT_LEAST, 90), OPEN)
		self.assertEqual(evaluate(None, RECORD_ONLY, 0), PASSED)

	def test_target_text(self):
		self.assertEqual(target_text(AT_LEAST, 90, "Percent"), "≥ 90%")
		self.assertEqual(target_text(AT_MOST, 14, "Day"), "≤ 14 Day")
		self.assertEqual(target_text(AT_MOST, 0, "Nos"), "≤ 0")


class IntegrationTestQualityMetrics(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("Quality Procedure", PROC):
			frappe.get_doc({"doctype": "Quality Procedure", "quality_procedure_name": PROC}).insert()
		company = ensure_company()
		cls.employee = frappe.db.get_value("Employee", {"status": "Active", "company": company}, "name")
		if not cls.employee:
			cls.employee = (
				frappe.get_doc(
					{
						"doctype": "Employee",
						"first_name": "_Test CAPA Owner",
						"gender": ensure_gender(),
						"date_of_birth": "1990-01-01",
						"date_of_joining": "2020-01-01",
						"company": company,
						"status": "Active",
					}
				)
				.insert()
				.name
			)

	def make_nc(self, severity="Critical", days_old=0, status="Open"):
		nc = frappe.get_doc(
			{
				"doctype": "Nonconformance Report",
				"subject": f"_Test metrics NC {frappe.generate_hash(length=6)}",
				"procedure": PROC,
				"status": "Open",
				"severity": severity,
			}
		).insert()
		if days_old:
			frappe.db.set_value(
				"Nonconformance Report",
				nc.name,
				"creation",
				now_datetime() - timedelta(days=days_old),
				update_modified=False,
			)
		if status != "Open":
			nc.reload()
			nc.status = status
			if status == "Resolved":
				nc.update({"disposition": "Rework to Specification", "quality_verification": "Accept"})
			nc.save()
		return nc

	def test_ncr_header_defaults_and_closure_rules(self):
		nc = self.make_nc(severity="Low")
		self.assertTrue(nc.ncr_date)
		self.assertEqual(nc.initiator, frappe.session.user)
		nc.status = "Resolved"
		self.assertRaises(frappe.ValidationError, nc.save)  # no disposition or QA acceptance
		nc.reload()
		nc.update({"status": "Resolved", "disposition": "Use As-Is", "quality_verification": "Accept"})
		self.assertRaises(frappe.ValidationError, nc.save)  # customer approval required
		nc.reload()
		nc.update(
			{
				"status": "Resolved",
				"disposition": "Repair",
				"auth_customer": "J. Buyer",
				"quality_verification": "Reject",
			}
		)
		self.assertRaises(frappe.ValidationError, nc.save)  # QA rejected the correction
		nc.reload()
		nc.update({"status": "Resolved", "disposition": "Other", "quality_verification": "Accept"})
		self.assertRaises(frappe.ValidationError, nc.save)  # Other needs a description
		nc.reload()
		nc.update(
			{
				"status": "Resolved",
				"disposition": "Other",
				"disposition_other": "Return to customer",
				"quality_verification": "Accept",
			}
		)
		nc.save()
		self.assertEqual(nc.status, "Resolved")
		nc.lot_qty, nc.reject_qty = 2, 3
		self.assertRaises(frappe.ValidationError, nc.save)

	def test_capa_numbering_due_dates_and_closure(self):
		from frappe.utils import add_days, getdate

		other = self.make_nc(severity="Low")
		nc = self.make_nc(severity="Low")
		nc.update(
			{
				"details": "<p>Ground lug loose</p>",
				"capa_required": 1,
				"capa_no": f"_T-CAPA-{frappe.generate_hash(length=6)}",
				"capa_initiated_date": "2026-10-01",
				"capa_related_ncrs": [{"non_conformance": other.name}],
			}
		)
		nc.save()
		self.assertTrue(nc.capa_no.startswith("_T-CAPA-"))
		# log numbers are unique across NCRs
		other.reload()
		other.update({"capa_required": 1, "capa_no": nc.capa_no})
		self.assertRaises(frappe.ValidationError, other.save)
		other.reload()
		other.capa_required = 1
		self.assertRaises(frappe.ValidationError, other.save)  # CAPA # required
		other.reload()
		ncr_no = f"_T-NCR-{frappe.generate_hash(length=6)}"
		frappe.db.set_value("Nonconformance Report", nc.name, "ncr_no", ncr_no, update_modified=False)
		other.ncr_no = f" {ncr_no} "
		self.assertRaises(frappe.ValidationError, other.save)
		other.reload()
		self.assertEqual(nc.capa_status, "Open")
		self.assertEqual(nc.capa_source, "NCR Trend")
		self.assertEqual(nc.capa_scar_reference, nc.capa_no)
		self.assertIn("Ground lug loose", nc.capa_finding)
		self.assertEqual(nc.why_problem, nc.subject)
		self.assertEqual(getdate(nc.capa_containment_due), getdate("2026-10-08"))
		self.assertEqual(getdate(nc.capa_correction_due), getdate("2026-10-31"))
		self.assertEqual(getdate(nc.capa_closure_due), getdate("2026-11-30"))
		# an extension needs an approver and a justification, and moves correction and closure
		nc.capa_extended_until = "2026-12-15"
		self.assertRaises(frappe.ValidationError, nc.save)
		nc.reload()
		nc.update(
			{
				"capa_extended_until": "2026-12-15",
				"capa_extension_approved_by": self.employee,
				"capa_extension_justification": "Supplier lead time",
			}
		)
		nc.save()
		self.assertEqual(getdate(nc.capa_closure_due), getdate("2026-12-15"))
		# closing needs the whys, root cause, corrective action and an Effective verification
		nc.capa_status = "Closed"
		self.assertRaises(frappe.ValidationError, nc.save)
		nc.reload()
		nc.update(
			{
				"capa_status": "Closed",
				"why_1": "Lug not torqued",
				"why_2": "Torque step missing from traveler",
				"capa_corrective_action": "<p>Add torque step</p>",
				"capa_quality_verification": "Not Effective",
				"capa_verified_by": self.employee,
				"capa_verification_date": add_days("2026-10-01", 20),
				"capa_closed_by": self.employee,
			}
		)
		self.assertRaises(frappe.ValidationError, nc.save)
		nc.reload()
		nc.update(
			{
				"capa_status": "Closed",
				"why_1": "Lug not torqued",
				"why_2": "Torque step missing from traveler",
				"capa_corrective_action": "<p>Add torque step</p>",
				"capa_quality_verification": "Effective",
				"capa_verified_by": self.employee,
				"capa_verification_date": add_days("2026-10-01", 20),
				"capa_closed_by": self.employee,
			}
		)
		nc.save()
		self.assertEqual(nc.capa_status, "Closed")
		self.assertEqual(nc.capa_root_cause, "Torque step missing from traveler")
		self.assertTrue(nc.capa_closure_date)
		# a CAPA cannot list its own NCR as related
		nc.append("capa_related_ncrs", {"non_conformance": nc.name})
		self.assertRaises(frappe.ValidationError, nc.save)

	def test_scar_numbering_defaults_and_approval(self):
		nc = self.make_nc(severity="Low")
		nc.update({"lot_qty": 10, "reject_qty": 3, "drawing_no": "D-100 Rev B", "details": "Burr on bore"})
		nc.scar_required = 1
		self.assertRaises(frappe.ValidationError, nc.save)  # SCAR Number is typed in from the log
		nc.reload()
		scar_no = f"_T-SCAR-{frappe.generate_hash(length=6)}"
		nc.update({"lot_qty": 10, "reject_qty": 3, "drawing_no": "D-100 Rev B", "details": "Burr on bore"})
		nc.update({"scar_required": 1, "scar_no": f"  {scar_no} "})
		self.assertRaises(frappe.ValidationError, nc.save)  # supplier name required
		nc.reload()
		nc.update({"lot_qty": 10, "reject_qty": 3, "drawing_no": "D-100 Rev B", "details": "Burr on bore"})
		nc.update({"scar_required": 1, "scar_no": f"  {scar_no} ", "scar_supplier_name": "_Test Supplier Co"})
		nc.save()
		self.assertEqual(nc.scar_no, scar_no)
		self.assertEqual(nc.scar_status, "Issued")
		self.assertTrue(nc.scar_issued_date)
		self.assertEqual(nc.scar_qty_received, 10)
		self.assertEqual(nc.scar_qty_rejected, 3)
		self.assertEqual(nc.scar_drawing_rev, "D-100 Rev B")
		self.assertIn("Burr on bore", nc.scar_discrepancy)

		other = self.make_nc(severity="Low")
		other.update({"scar_required": 1, "scar_no": scar_no, "scar_supplier_name": "_Test Supplier Co"})
		self.assertRaises(frappe.ValidationError, other.save)  # SCAR numbers are unique

		nc.reload()
		nc.scar_status = "Rejected"
		self.assertRaises(frappe.ValidationError, nc.save)  # reason and rejected by required
		nc.reload()
		nc.update(
			{
				"scar_status": "Rejected",
				"scar_rejection_reason": "Root cause not supported",
				"scar_rejected_by": self.employee,
			}
		)
		nc.save()
		self.assertTrue(nc.scar_rejected_date)

		nc.scar_status = "Approved"
		self.assertRaises(frappe.ValidationError, nc.save)  # supplier response incomplete
		nc.reload()
		nc.update(
			{
				"scar_status": "Approved",
				"scar_root_cause": "Worn deburr tool",
				"scar_containment": "Verified Complete",
				"scar_corrective_action": "Tool life limit added",
				"scar_approved_by": self.employee,
			}
		)
		nc.save()
		self.assertTrue(nc.scar_approved_date)
		self.assertTrue(nc.scar_response_received)

		html = frappe.get_print("Nonconformance Report", nc.name, print_format="QM-134 SCAR Report")
		self.assertIn(scar_no, html)
		self.assertIn("_Test Supplier Co", html)
		self.assertIn("Supplier Corrective Action Report", html)

	def test_legacy_non_conformance_is_moved_and_blocked(self):
		from hse.patches.move_non_conformance_to_nonconformance_report import execute

		self.assertRaises(
			frappe.ValidationError,
			frappe.get_doc(
				{
					"doctype": "Non Conformance",
					"subject": "_Test blocked",
					"procedure": PROC,
					"status": "Open",
				}
			).insert,
		)
		frappe.flags.in_migrate = True
		try:
			old = frappe.get_doc(
				{
					"doctype": "Non Conformance",
					"subject": "_Test legacy NC",
					"procedure": PROC,
					"status": "Open",
				}
			).insert()
		finally:
			frappe.flags.in_migrate = False
		comment = old.add_comment("Comment", "_Test legacy comment")
		execute()
		new = frappe.get_doc("Nonconformance Report", old.name)
		self.assertEqual(new.subject, "_Test legacy NC")
		self.assertEqual(new.owner, old.owner)
		self.assertEqual(
			frappe.db.get_value("Comment", comment.name, "reference_doctype"), "Nonconformance Report"
		)
		execute()  # running again does not duplicate
		self.assertEqual(frappe.db.count("Nonconformance Report", {"name": old.name}), 1)

	def test_resolved_on_stamped_and_cleared(self):
		nc = self.make_nc(severity="Low", status="Resolved")
		self.assertTrue(nc.resolved_on)
		nc.status = "Open"
		nc.save()
		self.assertFalse(nc.resolved_on)

	def test_open_critical_metric(self):
		nc = self.make_nc(days_old=10)
		value, detail = calculate("nc_open_critical_over_7_days", "2000-01-01", "2000-01-31")
		self.assertGreaterEqual(value, 1)
		self.assertIn(nc.name, detail)

	def test_review_calculates_and_failed_review_creates_action(self):
		self.make_nc(days_old=10)
		if frappe.db.exists("Quality Goal", GOAL):
			frappe.delete_doc("Quality Goal", GOAL, force=1)
		goal = frappe.get_doc(
			{
				"doctype": "Quality Goal",
				"goal": GOAL,
				"frequency": "None",
				"objectives": [
					{
						"hse_metric": "nc_open_critical_over_7_days",
						"target_operator": AT_MOST,
						"target_value": 0,
					},
					{"hse_metric": "nc_opened", "target_operator": RECORD_ONLY},
				],
			}
		).insert()
		self.assertEqual(goal.objectives[0].target, "≤ 0")
		self.assertTrue(goal.objectives[0].objective)

		review = frappe.get_doc({"doctype": "Quality Review", "goal": GOAL, "date": "2026-10-01"}).insert()
		self.assertEqual(str(review.period_start), "2026-09-01")
		self.assertEqual(str(review.period_end), "2026-09-30")
		rows = {r.hse_metric: r for r in review.reviews}
		self.assertEqual(rows["nc_open_critical_over_7_days"].status, FAILED)
		self.assertEqual(rows["nc_opened"].status, PASSED)
		self.assertEqual(review.status, FAILED)
		self.assertTrue(review.metrics_calculated_on)

		action = frappe.db.get_value(
			"Quality Action", {"review": review.name}, ["name", "corrective_preventive"]
		)
		self.assertTrue(action)
		self.assertEqual(action[1], "Corrective")

		# Saving again does not create a second action
		review.save()
		self.assertEqual(frappe.db.count("Quality Action", {"review": review.name}), 1)


class IntegrationTestStarterGoalsButton(IntegrationTestCase):
	def test_button_creates_missing_goals_once(self):
		from hse.quality_metrics.events import create_starter_goals, get_missing_starter_goals
		from hse.quality_metrics.starter_goals import STARTER_GOALS

		names = [g["goal"] for g in STARTER_GOALS]
		for n in names:
			if frappe.db.exists("Quality Goal", n):
				frappe.delete_doc("Quality Goal", n, force=1)
		self.assertEqual(sorted(get_missing_starter_goals()), sorted(names))

		result = create_starter_goals()
		self.assertEqual(sorted(result["created"]), sorted(names))
		self.assertEqual(get_missing_starter_goals(), [])
		goal = frappe.get_doc("Quality Goal", "Housekeeping")
		self.assertEqual(goal.frequency, "Monthly")
		self.assertTrue(all(o.hse_metric for o in goal.objectives))

		again = create_starter_goals()
		self.assertEqual(again["created"], [])
		self.assertEqual(sorted(again["existing"]), sorted(names))

	def test_button_requires_quality_role(self):
		from hse.quality_metrics.events import create_starter_goals

		user = "test-no-quality-role@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc(
				{"doctype": "User", "email": user, "first_name": "No Quality Role", "send_welcome_email": 0}
			).insert()
		frappe.set_user(user)
		try:
			with self.assertRaises(frappe.PermissionError):
				create_starter_goals()
		finally:
			frappe.set_user("Administrator")
