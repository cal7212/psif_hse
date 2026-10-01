# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Idempotent setup for SDS tracking, run after install and every migrate."""

import frappe
from frappe.permissions import add_permission, update_permission_property

GHS_PICTOGRAMS = [
	("Exploding Bomb", "GHS01", "Explosives, self-reactives, organic peroxides"),
	("Flame", "GHS02", "Flammables, pyrophorics, self-heating, emits flammable gas"),
	("Flame Over Circle", "GHS03", "Oxidizers"),
	("Gas Cylinder", "GHS04", "Gases under pressure"),
	("Corrosion", "GHS05", "Skin corrosion/burns, eye damage, corrosive to metals"),
	("Skull and Crossbones", "GHS06", "Acute toxicity (fatal or toxic)"),
	("Exclamation Mark", "GHS07", "Irritant, skin sensitizer, acute toxicity (harmful), narcotic effects"),
	("Health Hazard", "GHS08", "Carcinogen, mutagen, reproductive toxicity, respiratory sensitizer, target organ toxicity, aspiration"),
	("Environment", "GHS09", "Aquatic toxicity (non-mandatory under OSHA)"),
]

# role -> permissions on SDS. Employee read gives access to the attached SDS files.
SDS_PERMS = {
	"Employee": ["read", "print", "report"],
	"Quality Manager": ["read", "write", "create", "print", "report", "export", "email", "share"],
}


def after_install():
	setup()


def after_migrate():
	setup()


def setup():
	make_pictograms()
	ensure_sds_permissions()


def make_pictograms():
	for name, code, hazards in GHS_PICTOGRAMS:
		if not frappe.db.exists("GHS Pictogram", name):
			frappe.get_doc(
				{"doctype": "GHS Pictogram", "pictogram_name": name, "ghs_code": code, "hazards": hazards}
			).insert(ignore_permissions=True)


def ensure_sds_permissions():
	"""SDS existed as a custom DocType, so its saved permissions are kept on migrate.
	Add the extra roles as Custom DocPerm rules instead."""
	for role, ptypes in SDS_PERMS.items():
		if not frappe.db.exists("Role", role):
			continue
		if not frappe.db.exists("Custom DocPerm", {"parent": "SDS", "role": role, "permlevel": 0, "if_owner": 0}):
			add_permission("SDS", role, 0)
		for ptype in ptypes:
			update_permission_property("SDS", role, 0, ptype, 1, validate=False)
	frappe.clear_cache(doctype="SDS")
