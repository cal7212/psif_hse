import unittest
from types import SimpleNamespace
from unittest.mock import patch
from hse.service_requests import events


class TestEventBoundaries(unittest.TestCase):
    def test_disabled_without_settings(self):
        with patch.object(events.frappe.db, "exists", return_value=False):
            self.assertFalse(events.enabled())

    def test_disabled_without_installed_field(self):
        meta = SimpleNamespace(has_field=lambda name: False)
        with patch.object(events.frappe.db, "exists", return_value=True), patch.object(events.frappe, "get_meta", return_value=meta):
            self.assertFalse(events.enabled())

    def test_disabled_validation_is_noop(self):
        with patch.object(events, "enabled", return_value=False):
            events.validate(None)
            events.on_update(None)

    def test_website_user_is_not_internal_agent(self):
        with patch.object(events.frappe, "session", SimpleNamespace(user="external@example.com")), patch.object(events.frappe, "get_cached_value", return_value="Website User"):
            self.assertFalse(events.agent())

    def test_internal_agent_role(self):
        with patch.object(events.frappe, "session", SimpleNamespace(user="tech@example.com")), patch.object(events.frappe, "get_cached_value", return_value="System User"), patch.object(events.frappe, "get_roles", return_value=["Agent"]):
            self.assertTrue(events.agent())
            self.assertFalse(events.manager())

    def test_legacy_status(self):
        doc = SimpleNamespace(status="Resolved", meta=SimpleNamespace(get_field=lambda name: SimpleNamespace(fieldtype="Select")))
        self.assertTrue(events.terminal(doc))
        doc.status = "Open"
        self.assertFalse(events.terminal(doc))

    def test_custom_resolved_category(self):
        doc = SimpleNamespace(status="Verified Complete", meta=SimpleNamespace(get_field=lambda name: SimpleNamespace(fieldtype="Link", options="HD Ticket Status")))
        with patch.object(events.frappe.db, "get_value", return_value="Resolved"):
            self.assertTrue(events.terminal(doc))
