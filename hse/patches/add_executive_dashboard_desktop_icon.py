"""Put the Executive Dashboard on the Desk. Runs once."""

from hse.patches.add_hse_home_desktop_icon import ensure_desktop_icon


def execute():
	ensure_desktop_icon("Executive Dashboard", "/app/executive-dashboard")
