# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Rename the Small Assembly shop to Light Assembly, load the sample inspection templates,
and relabel the Shop QC links on the Systems workspace. Safe to re-run."""

import frappe

from hse.shop_qc.install import create_sample_templates

OLD_SHOP, NEW_SHOP = "Small Assembly", "Light Assembly"
WORKSPACE = "Systems"
LABELS = {
	"HPU QA Checks": "Shop QC",
	"HPU Information": "QC Units",
	"HPU QC Doc": "QC Inspections",
	"HPU QC Template": "QC Inspection Templates",
	"HPU Build Stage Definition": "QC Stages",
}


def execute():
	rename_light_assembly()
	create_sample_templates()
	relabel_workspace()


def rename_light_assembly():
	if frappe.db.exists("Build Shop", OLD_SHOP) and not frappe.db.exists("Build Shop", NEW_SHOP):
		frappe.rename_doc("Build Shop", OLD_SHOP, NEW_SHOP, force=True)
		shop = frappe.get_doc("Build Shop", NEW_SHOP)
		shop.shop_name = NEW_SHOP
		if shop.inspection_prefix == "SAI" and not frappe.db.exists(
			"QC Inspection", {"name": ("like", "SAI-%")}
		):
			shop.inspection_prefix = "LAI"
		if shop.certificate_title:
			shop.certificate_title = shop.certificate_title.replace(OLD_SHOP, NEW_SHOP)
		shop.save(ignore_permissions=True)

	for stage in frappe.get_all("QC Stage", filters={"name": ("like", "SA - %")}, pluck="name"):
		new = "LA - " + stage[len("SA - ") :]
		if not frappe.db.exists("QC Stage", new):
			frappe.rename_doc("QC Stage", stage, new, force=True)
			frappe.db.set_value("QC Stage", new, "stage_name", new, update_modified=False)


def relabel_workspace():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return
	ws = frappe.get_doc("Workspace", WORKSPACE)
	links = {link.link_to for link in ws.links if link.type == "Link"}
	changed = False
	for link in ws.links:
		if link.label in LABELS:
			link.label = LABELS[link.label]
			changed = True
	if "Build Shop" not in links and any(link.link_to == "QC Inspection" for link in ws.links):
		card = next(
			(link for link in ws.links if link.type == "Card Break" and link.label == "Shop QC"), None
		)
		after = next(link for link in ws.links if link.link_to == "QC Inspection")
		new = ws.append(
			"links",
			{"type": "Link", "label": "Build Shops", "link_type": "DocType", "link_to": "Build Shop"},
		)
		# move the new link right after QC Inspections, inside the Shop QC card
		ws.links.remove(new)
		ws.links.insert(ws.links.index(after) + 1, new)
		for i, link in enumerate(ws.links, 1):
			link.idx = i
		if card:
			card.link_count = (card.link_count or 0) + 1
		changed = True
	if ws.content and '"HPU QA Checks"' in ws.content:
		ws.content = ws.content.replace('"HPU QA Checks"', '"Shop QC"')
		changed = True
	if changed:
		ws.save(ignore_permissions=True)
