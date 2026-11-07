# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Executive Dashboard as the home page for managers (Manager Home Settings).

A manager is a user who (rules can be switched off in the settings):
- is linked (Employee.user_id) to an employee that at least one Active employee reports to, or
- has the System Manager role, or
- is listed under "Also include".
"Exclude" wins over every rule. Administrator, Guest, disabled users and Website Users are
never included.

How the landing works in Frappe v16:
- Login: LoginManager.post_login runs the on_session_creation hooks (make_session) before
  set_user_info, and set_user_info takes the home page from website.utils.get_home_page(),
  which returns frappe.local.flags.home_page when set. So on_session_creation sets that flag.
  A redirect-to link (for example from an email) still wins in the login page.
- Apps screen: boot carries hse_manager_home; hse_nav.js sends a manager from the /desk apps
  screen to the home page the first time in a browser tab.
"""

import frappe
from frappe import _

SETTINGS = "Manager Home Settings"
DEFAULT_HOME = "/app/executive-dashboard"
NEVER = {"Administrator", "Guest"}


def _settings():
	try:
		return frappe.get_cached_doc(SETTINGS)
	except Exception:
		return None


def _system_users() -> set[str]:
	return (
		set(frappe.get_all("User", filters={"enabled": 1, "user_type": "System User"}, pluck="name")) - NEVER
	)


def managers(settings=None) -> dict[str, list[str]]:
	"""{user: [reasons]} for everyone the rules include, before Exclude."""
	s = settings or _settings()
	if not s:
		return {}
	users = _system_users()
	out: dict[str, list[str]] = {}

	def add(user, reason):
		if user in users:
			out.setdefault(user, []).append(reason)

	if s.include_direct_reports and frappe.db.table_exists("Employee"):
		bosses = set(
			frappe.get_all(
				"Employee",
				filters={"status": "Active", "reports_to": ["is", "set"]},
				pluck="reports_to",
			)
		)
		if bosses:
			for u in frappe.get_all(
				"Employee", filters={"name": ["in", list(bosses)], "user_id": ["is", "set"]}, pluck="user_id"
			):
				add(u, _("Has direct reports"))
	if s.include_system_managers:
		for u in frappe.get_all(
			"Has Role", filters={"role": "System Manager", "parenttype": "User"}, pluck="parent"
		):
			add(u, _("System Manager"))
	for row in s.include_users or []:
		add(row.user, _("Also include"))
	return out


def _excluded(settings) -> set[str]:
	return {r.user for r in (settings.exclude_users or [])} | NEVER


def home_for(user: str | None = None) -> str | None:
	"""The manager home page for `user`, or None to keep the usual landing."""
	user = user or frappe.session.user
	if user in NEVER:
		return None
	s = _settings()
	if not s or not s.enabled or user in _excluded(s):
		return None
	if user not in managers(s):
		return None
	return s.home_page or DEFAULT_HOME


def on_session_creation(login_manager=None):
	"""Login hook: send managers to the Executive Dashboard."""
	try:
		home = home_for(frappe.session.user)
	except Exception:
		frappe.log_error(title="Manager home page")
		return
	if home:
		frappe.local.flags.home_page = home


def boot_session(bootinfo):
	try:
		bootinfo.hse_manager_home = home_for(frappe.session.user)
	except Exception:
		bootinfo.hse_manager_home = None


@frappe.whitelist()
def preview() -> dict:
	"""Read-only: the users the saved rules send to the home page, with the reasons."""
	frappe.only_for("System Manager")
	s = _settings()
	if not s:
		return {"enabled": 0, "users": [], "excluded": [], "home_page": DEFAULT_HOME}
	found = managers(s)
	excluded = _excluded(s)
	names = dict(
		frappe.get_all(
			"User", filters={"name": ["in", list(found) or [""]]}, fields=["name", "full_name"], as_list=True
		)
	)
	users = [
		{"user": u, "full_name": names.get(u), "reasons": reasons}
		for u, reasons in sorted(found.items(), key=lambda kv: (names.get(kv[0]) or kv[0]).lower())
		if u not in excluded
	]
	return {
		"enabled": s.enabled,
		"home_page": s.home_page or DEFAULT_HOME,
		"users": users,
		"excluded": sorted(u for u in found if u in excluded),
	}
