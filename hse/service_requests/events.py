import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime
from hse.service_requests.rules import P, PUBLIC, value, ready, validate_rules, closure_error

MANAGERS = {"System Manager", "Agent Manager"}


def enabled():
    return bool(frappe.db.exists("DocType", "HD Settings") and
                frappe.get_meta("HD Settings").has_field(P + "service_requests_enabled") and
                cint(frappe.db.get_single_value("HD Settings", P + "service_requests_enabled")))


def agent():
    return (frappe.session.user == "Administrator" or
            (frappe.get_cached_value("User", frappe.session.user, "user_type") == "System User"
             and bool(set(frappe.get_roles()) & (MANAGERS | {"Agent"}))))


def manager():
    return agent() and (frappe.session.user == "Administrator" or bool(set(frappe.get_roles()) & MANAGERS))


def terminal(doc):
    field = doc.meta.get_field("status")
    if field and field.fieldtype == "Link" and field.options == "HD Ticket Status":
        category = frappe.db.get_value("HD Ticket Status", doc.status, "category")
        if category is None:
            frappe.throw(_("Unknown status category; review service closure rules."))
        return category == "Resolved" or doc.status == "Closed"
    return doc.status in {"Resolved", "Closed"}


def validate(doc, method=None):
    if not enabled():
        return
    previous = doc.get_doc_before_save()
    changed = [f.fieldname for f in doc.meta.fields if f.fieldname.startswith(P)
               and doc.get(f.fieldname) != (previous.get(f.fieldname) if previous else None)
               and (previous or doc.get(f.fieldname) not in (None, "", 0))]
    if not agent():
        for key in changed:
            if key not in PUBLIC or (previous and value(previous, "triaged")):
                frappe.throw(_("Only internal agents may update service tracking after triage."), frappe.PermissionError)
    if previous and value(previous, "category") and not value(doc, "category"):
        frappe.throw(_("Service category cannot be removed to bypass validation."))
    if not value(doc, "category"):
        if any(value(doc, key) for key in ("triaged", "repair", "work_type", "route")):
            frappe.throw(_("Select a service category."))
        return
    try:
        validate_rules(doc.as_dict(), get_datetime)
    except ValueError as error:
        frappe.throw(str(error))
    if value(doc, "owner"):
        owner = frappe.get_doc("User", value(doc, "owner"))
        if not owner.enabled or owner.user_type != "System User":
            frappe.throw(_("Internal owner must be an enabled system user."))
    if value(doc, "asset"):
        frappe.get_doc("Asset", value(doc, "asset")).check_permission("read")
    repair_name = value(doc, "repair")
    repair = frappe.get_doc("Asset Repair", repair_name) if repair_name else None
    if repair and repair.asset != value(doc, "asset"):
        frappe.throw(_("Ticket and repair assets must match."))
    if repair_name and (not previous or repair_name != value(previous, "repair")):
        if not doc.flags.get("hse_repair_link_authorized"):
            frappe.throw(_("Use the authorized Link Existing Repair action."))
    if previous and value(previous, "repair") and not repair_name:
        frappe.throw(_("Retain the repair link for audit history."))
    if previous and terminal(previous) and not terminal(doc):
        doc.custom_hse_verified = None
        if value(doc, "stage") == "Closed":
            doc.custom_hse_stage = "Triage"
    if terminal(doc) or value(doc, "stage") == "Closed":
        duplicate_valid = False
        target = value(doc, "duplicate_of")
        if target and str(target) != str(doc.name):
            primary = frappe.get_doc("HD Ticket", target)
            primary.check_permission("read")
            duplicate_valid = bool(value(primary, "category") == value(doc, "category") and
                                   value(primary, "asset") == value(doc, "asset") and
                                   value(primary, "closure_type") != "Duplicate")
        error = closure_error(doc.as_dict(), repair.as_dict() if repair else None,
                              manager=manager(), duplicate_valid=duplicate_valid)
        if error:
            frappe.throw(_(error))
    if value(doc, "stage") == "Closed" and not terminal(doc):
        frappe.throw(_("Resolve native ticket status before closing its work stage."))
    for key in ("failure_date", "outage_start", "restored", "provider_sent", "provider_completed", "verified"):
        if value(doc, key) and get_datetime(value(doc, key)) > now_datetime():
            frappe.throw(_("Actual timestamp cannot be in the future: ") + key)


def on_update(doc, method=None):
    if not enabled() or not agent() or not ready(doc.as_dict()) or value(doc, "repair"):
        return
    if value(doc, "closure_type") in {"Duplicate", "Cancelled"}:
        return
    frappe.db.sql("SELECT name FROM `tabHD Ticket` WHERE name=%s FOR UPDATE", (doc.name,))
    existing = frappe.db.get_value("HD Ticket", doc.name, P + "repair")
    if not existing:
        existing = frappe.db.get_value("Asset Repair", {"custom_hse_source_ticket": doc.name}, "name")
    if not existing:
        asset = frappe.get_doc("Asset", value(doc, "asset"))
        asset.check_permission("read")
        repair = frappe.new_doc("Asset Repair")
        repair.update({"asset": asset.name, "company": asset.company,
                       "failure_date": value(doc, "failure_date"), "repair_status": "Pending",
                       "description": doc.subject, "custom_hse_source_ticket": doc.name})
        repair.insert()
        existing = repair.name
    doc.db_set(P + "repair", existing, update_modified=False)


@frappe.whitelist()
def link_existing_repair(ticket_name: str, repair_name: str) -> dict:
    if not enabled() or not agent():
        frappe.throw(_("Internal service agent required."), frappe.PermissionError)
    doc = frappe.get_doc("HD Ticket", ticket_name)
    doc.check_permission("write")
    repair = frappe.get_doc("Asset Repair", repair_name)
    repair.check_permission("read")
    if not value(doc, "category") or value(doc, "repair") or repair.docstatus == 2:
        frappe.throw(_("Records are not eligible for linking."))
    if not value(doc, "asset") or value(doc, "asset") != repair.asset:
        frappe.throw(_("Choose a repair for the same asset."))
    doc.flags.hse_repair_link_authorized = True
    doc.custom_hse_repair = repair.name
    doc.save()
    return {"ticket": doc.name, "repair": repair.name}


def validate_repair(doc, method=None):
    if not enabled():
        return
    previous = doc.get_doc_before_save()
    source = doc.get("custom_hse_source_ticket")
    if previous and source != previous.get("custom_hse_source_ticket"):
        frappe.throw(_("Source ticket is immutable."))
    tickets = frappe.get_all("HD Ticket", filters={P + "repair": doc.name}, fields=["name", P + "asset"])
    for ticket in tickets:
        if value(ticket, "asset") != doc.asset:
            frappe.throw(_("Repair asset must match all linked tickets."))
    if source:
        ticket = frappe.get_doc("HD Ticket", source)
        ticket.check_permission("write")
        if not agent() or not value(ticket, "category") or value(ticket, "asset") != doc.asset:
            frappe.throw(_("Invalid source service ticket."), frappe.PermissionError)
    if doc.failure_date and doc.completion_date and get_datetime(doc.completion_date) < get_datetime(doc.failure_date):
        frappe.throw(_("Repair completion cannot precede failure."))


def protect_repair_removal(doc, method=None):
    if not enabled():
        return
    names = frappe.get_all("HD Ticket", filters={P + "repair": doc.name}, pluck="name")
    if names and method == "on_trash":
        frappe.throw(_("Linked repair history cannot be deleted."))
    if any(terminal(frappe.get_doc("HD Ticket", name)) for name in names):
        frappe.throw(_("Reopen linked tickets before cancelling the repair."))
