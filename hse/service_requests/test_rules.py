import unittest
from datetime import datetime
from hse.service_requests.rules import P, ready, validate_rules, closure_error


class TestServiceRules(unittest.TestCase):
    def data(self, **changes):
        values = dict(category="Equipment Maintenance", work_type="Repair", triaged=1,
                      owner="tech@example.com", route="Internal", asset="A-1",
                      failure_date="2026-11-01T08:00:00", repair_ack=1, verified="2026-11-01T12:00:00")
        values.update(changes)
        return {P + key: val for key, val in values.items()}

    def test_ready(self):
        self.assertTrue(ready(self.data()))

    def test_ack_required(self):
        self.assertFalse(ready(self.data(repair_ack=0)))
        with self.assertRaises(ValueError):
            validate_rules(self.data(repair_ack=0), datetime.fromisoformat)

    def test_failure_required(self):
        self.assertFalse(ready(self.data(failure_date=None)))

    def test_routine_not_repair(self):
        self.assertFalse(ready(self.data(work_type="Routine Maintenance")))

    def test_owner_required(self):
        with self.assertRaises(ValueError):
            validate_rules(self.data(owner=None), datetime.fromisoformat)

    def test_provider_required(self):
        with self.assertRaises(ValueError):
            validate_rules(self.data(route="Other Contractor"), datetime.fromisoformat)

    def test_negative_outage(self):
        with self.assertRaises(ValueError):
            validate_rules(self.data(outage_start="2026-11-01T10:00:00", restored="2026-11-01T09:00:00"), datetime.fromisoformat)

    def test_restoration_requires_start(self):
        with self.assertRaises(ValueError):
            validate_rules(self.data(restored="2026-11-01T09:00:00"), datetime.fromisoformat)

    def test_open_outage_allowed(self):
        validate_rules(self.data(outage_start="2026-11-01T09:00:00"), datetime.fromisoformat)

    def test_missing_repair(self):
        self.assertIsNotNone(closure_error(self.data()))

    def test_pending_repair(self):
        self.assertIsNotNone(closure_error(self.data(), {"docstatus": 0, "repair_status": "Pending"}))

    def test_completed_draft(self):
        self.assertIsNotNone(closure_error(self.data(), {"docstatus": 0, "repair_status": "Completed"}))

    def test_completed_submitted(self):
        self.assertIsNone(closure_error(self.data(), {"docstatus": 1, "repair_status": "Completed"}))

    def test_verification_required(self):
        self.assertIsNotNone(closure_error(self.data(verified=None), {"docstatus": 1, "repair_status": "Completed"}))

    def test_cancel_manager(self):
        d = self.data(closure_type="Cancelled", closure_reason="Not required")
        self.assertIsNotNone(closure_error(d))
        self.assertIsNone(closure_error(d, manager=True))

    def test_duplicate_target(self):
        d = self.data(closure_type="Duplicate", closure_reason="Same event")
        self.assertIsNotNone(closure_error(d, manager=True))
        self.assertIsNone(closure_error(d, manager=True, duplicate_valid=True))

    def test_nonasset_reason(self):
        self.assertIsNotNone(closure_error(self.data(asset=None)))
        self.assertIsNone(closure_error(self.data(asset=None, closure_type="Non-asset Work", closure_reason="Unregistered fixture")))

    def test_invalid_category(self):
        with self.assertRaises(ValueError):
            validate_rules(self.data(category="Other"), datetime.fromisoformat)
