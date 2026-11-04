"""Put Shop QC Home on the Desk. Runs once."""

from hse.patches.add_hse_home_desktop_icon import ensure_desktop_icon


def execute():
	ensure_desktop_icon("Shop QC Home", "/app/shop-qc-home")
