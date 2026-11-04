import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from hse.service_requests.rules import P, PUBLIC


def ticket_fields():
    specs = [
        ("category", "Service Category", "Select", "\nBuilding Maintenance\nIT\nEquipment Maintenance"),
        ("location", "Location", "Link", "Location"), ("asset", "Asset", "Link", "Asset"),
        ("equipment_description", "Equipment / Building Description", "Small Text", None),
        ("work_type", "Work Type", "Select", "\nRepair\nRoutine Maintenance\nInspection\nService Request"),
        ("owner", "Internal Owner", "Link", "User"),
        ("route", "Fulfillment Route", "Select", "\nInternal\nOnsite\nOther Contractor"),
        ("provider", "External Provider", "Data", None),
        ("external_reference", "External Reference", "Data", None),
        ("stage", "Work Stage", "Select", "\nTriage\nAssigned\nIn Progress\nAwaiting Provider\nAwaiting Parts\nAwaiting Approval\nVerification\nClosed"),
        ("triaged", "Triage Confirmed", "Check", None),
        ("failure_date", "Failure Date", "Datetime", None),
        ("repair_ack", "Acknowledge Asset Repair may mark asset Out of Order", "Check", None),
        ("repair", "Asset Repair", "Link", "Asset Repair"),
        ("outage_start", "Actual Outage Start", "Datetime", None),
        ("restored", "Actual Service Restoration", "Datetime", None),
        ("provider_sent", "Sent to Provider", "Datetime", None),
        ("provider_due", "Provider Due", "Datetime", None),
        ("provider_completed", "Provider Completed", "Datetime", None),
        ("verified", "Internally Verified On", "Datetime", None),
        ("closure_type", "Closure Type", "Select", "\nNormal\nDuplicate\nCancelled\nNon-asset Work"),
        ("closure_reason", "Closure / Exception Reason", "Small Text", None),
        ("duplicate_of", "Duplicate Of", "Link", "HD Ticket"),
    ]
    fields = []
    for key, label, kind, options in specs:
        name = P + key
        row = {"fieldname": name, "label": label, "fieldtype": kind, "no_copy": 1,
               "permlevel": 0 if name in PUBLIC else 8,
               "insert_after": fields[-1]["fieldname"] if fields else "description"}
        if options:
            row["options"] = options
        if key == "repair":
            row["read_only"] = 1
        fields.append(row)
    return fields


def after_migrate():
    if not frappe.db.exists("DocType", "HD Ticket"):
        return
    for name in ("HD Settings", "Asset Repair"):
        if not frappe.db.exists("DocType", name):
            frappe.throw("Service request dependency is missing: " + name)
    create_custom_fields({
        "HD Ticket": ticket_fields(),
        "HD Settings": [{"fieldname": P + "service_requests_enabled", "label": "Enable HSE Service Requests",
                         "fieldtype": "Check", "default": "0"}],
        "Asset Repair": [{"fieldname": "custom_hse_source_ticket", "label": "Source Service Request",
                          "fieldtype": "Link", "options": "HD Ticket", "insert_after": "asset",
                          "read_only": 1, "no_copy": 1, "unique": 1}],
    }, update=True)


def configure_template(template_name="Default"):
    frappe.only_for("System Manager")
    if not frappe.get_meta("HD Ticket Template Field").has_field("visible_to"):
        frappe.throw("Installed Helpdesk lacks expected template visibility support.")
    doc = frappe.get_doc("HD Ticket Template", template_name)
    rows = {row.fieldname: row for row in doc.fields}
    for field in ticket_fields():
        name = field["fieldname"]
        row = rows.get(name) or doc.append("fields", {"fieldname": name})
        row.visible_to = "Everyone" if name in PUBLIC else "Agents"
        row.required = 0
        row.editable_after_creation = 0
    doc.save()
    return doc.name
