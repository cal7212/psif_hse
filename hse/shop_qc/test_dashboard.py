# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""bench --site <test-site> run-tests --module hse.shop_qc.test_dashboard"""

import json
from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from hse.shop_qc import dashboard
from hse.shop_qc.report.qc_unit_build_status import qc_unit_build_status as report

HERE = Path(__file__).parent


def _files(folder):
	return [json.loads(p.read_text()) for p in sorted((HERE / folder).glob("*/*.json"))]


class UnitTestShopQCDashboard(UnitTestCase):
	def test_summarise_progress(self):
		stages = [frappe._dict(name=n) for n in ("Assembly", "Test", "Final Release")]
		p = dashboard.summarise_progress(stages, {"Assembly": 1})
		self.assertEqual((p["stages_accepted"], p["stages_total"], p["next_stage"]), (1, 3, "Test"))
		self.assertEqual(p["progress"], 33.3)
		done = dashboard.summarise_progress(stages, {"Assembly": 1, "Test": 1, "Final Release": 1})
		self.assertEqual((done["progress"], done["next_stage"]), (100, None))
		self.assertEqual(dashboard.summarise_progress([], {})["progress"], 0)

	def test_empty_metric_shows_a_dash(self):
		self.assertEqual(dashboard._card(None, "Percent"), dashboard.NO_VALUE)
		self.assertEqual(dashboard._card(0)["value"], 0)

	def test_workspace_points_at_shipped_cards_and_charts(self):
		ws = json.loads((HERE / "workspace" / "shop_qc" / "shop_qc.json").read_text())
		cards = {c["name"] for c in _files("number_card")}
		charts = {c["name"] for c in _files("dashboard_chart")}
		quick_lists = {q["label"] for q in ws["quick_lists"]}
		shortcuts = {s["label"] for s in ws["shortcuts"]}
		link_cards = {lnk["label"] for lnk in ws["links"] if lnk["type"] == "Card Break"}
		blocks = {b["custom_block_name"] for b in ws["custom_blocks"]}
		self.assertEqual(blocks, set(dashboard.WORKSPACE_BLOCKS))
		self.assertEqual({c["number_card_name"] for c in ws["number_cards"]}, cards)
		self.assertEqual({c["chart_name"] for c in ws["charts"]}, charts)
		# The desk matches a content block to its widget row by the row's label, not the record name.
		card_labels = {c["label"] for c in ws["number_cards"]}
		chart_labels = {c["label"] for c in ws["charts"]}
		block_labels = {b["label"] for b in ws["custom_blocks"]}
		for block in json.loads(ws["content"]):
			data = block["data"]
			if block["type"] == "number_card":
				self.assertIn(data["number_card_name"], card_labels)
			elif block["type"] == "chart":
				self.assertIn(data["chart_name"], chart_labels)
			elif block["type"] == "quick_list":
				self.assertIn(data["quick_list_name"], quick_lists)
			elif block["type"] == "shortcut":
				self.assertIn(data["shortcut_name"], shortcuts)
			elif block["type"] == "card":
				self.assertIn(data["card_name"], link_cards)
			elif block["type"] == "custom_block":
				self.assertIn(data["custom_block_name"], block_labels)

	def test_block_files_exist(self):
		for stem in dashboard.WORKSPACE_BLOCKS.values():
			for ext in ("html", "js", "css"):
				self.assertTrue((dashboard.BLOCKS_DIR / f"{stem}.{ext}").is_file(), f"{stem}.{ext}")

	def test_sidebar_opens_the_workspace(self):
		sidebar = json.loads((HERE / "sidebar" / "shop_qc" / "shop_qc.json").read_text())
		self.assertEqual(
			(sidebar["doctype"], sidebar["module"], sidebar["title"]), ("Sidebar", "Shop QC", "Shop QC")
		)
		home = sidebar["items"][0]
		self.assertEqual((home["link_type"], home["link_to"]), ("Workspace", "Shop QC"))
		linked = {i["link_to"] for i in sidebar["items"] if i["type"] == "Link"}
		self.assertIn("QC Unit Build Status", linked)
		self.assertIn("QC Inspection Template", linked)

	def test_custom_cards_call_whitelisted_methods(self):
		for card in _files("number_card"):
			if card["type"] != "Custom":
				continue
			module, _sep, fn = card["method"].rpartition(".")
			self.assertEqual(module, "hse.shop_qc.dashboard", card["name"])
			self.assertIn(getattr(dashboard, fn), frappe.whitelisted, card["name"])


class IntegrationTestShopQCDashboard(IntegrationTestCase):
	def test_workspace_synced(self):
		self.assertTrue(frappe.db.exists("Workspace", "Shop QC"))
		for card in _files("number_card"):
			self.assertTrue(frappe.db.exists("Number Card", card["name"]), card["name"])
		for chart in _files("dashboard_chart"):
			self.assertTrue(frappe.db.exists("Dashboard Chart", chart["name"]), chart["name"])
		self.assertTrue(frappe.db.exists("Report", "QC Unit Build Status"))
		if frappe.db.exists("DocType", "Sidebar"):
			self.assertTrue(frappe.db.exists("Sidebar", "Shop QC"))

	def test_custom_cards_run(self):
		for fn in (
			dashboard.first_pass_yield,
			dashboard.units_released,
			dashboard.rejected_inspections,
			dashboard.shipped_before_release,
			dashboard.critical_ncrs_over_7_days,
			dashboard.units_with_missing_parts,
		):
			out = fn()
			self.assertTrue(out == dashboard.NO_VALUE or "value" in out, fn.__name__)

	def test_active_units_block(self):
		dashboard.make_workspace_blocks()
		block = frappe.get_doc("Custom HTML Block", "Shop QC Active Units")
		self.assertFalse(block.private)
		self.assertIn("hse.shop_qc.dashboard.active_units", block.script)
		dashboard.make_workspace_blocks()  # idempotent
		for u in dashboard.active_units():
			self.assertIn(u.status, dashboard.ACTIVE_STATUSES)
			self.assertIn("next_stage", u)

	def test_report_runs(self):
		columns, data, _msg, _chart = report.execute({"include_completed": 1})
		self.assertIn("next_stage", [c["fieldname"] for c in columns])
		for row in data:
			self.assertLessEqual(row["progress"], 100)
		_cols, active, *_rest = report.execute({})
		self.assertTrue(all(r["status"] in dashboard.ACTIVE_STATUSES for r in active))
