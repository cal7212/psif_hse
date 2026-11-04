"""Put HSE Home on the Desk.

Frappe only turns `add_to_apps_screen` into a Desktop Icon when an app is first installed, so a
site that already had HSE never got one for the new HSE Home page. Runs once."""

import frappe

LOGO = "/assets/hse/images/psif_logo.jpg"


def execute():
	ensure_desktop_icon("HSE Home", "/app/hse-home")


def ensure_desktop_icon(label: str, link: str):
	"""Create an App-style Desktop Icon that opens `link`, unless one with `label` exists."""
	if not frappe.db.table_exists("Desktop Icon") or frappe.db.exists("Desktop Icon", label):
		return
	icon = frappe.new_doc("Desktop Icon")
	icon.label = label
	icon.icon_type = "App"
	icon.link_type = "External"
	icon.link = link
	icon.app = "hse"
	icon.logo_url = LOGO
	icon.standard = 0
	icon.insert(ignore_permissions=True, ignore_links=True)
	try:
		from frappe.desk.doctype.desktop_icon.desktop_icon import clear_every_users_desktop_icons

		clear_every_users_desktop_icons()
	except ImportError:
		frappe.cache.delete_key("desktop_icons")
