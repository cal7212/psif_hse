P = "custom_hse_"
PUBLIC = {P + key for key in ("category", "location", "asset", "equipment_description")}


def value(doc, key):
    return doc.get(P + key)


def ready(doc):
    return bool(value(doc, "triaged") and value(doc, "work_type") == "Repair"
                and value(doc, "asset") and value(doc, "failure_date") and value(doc, "repair_ack"))


def validate_rules(doc, parse):
    options = {
        "category": {"Building Maintenance", "IT", "Equipment Maintenance"},
        "route": {"Internal", "Onsite", "Other Contractor"},
        "work_type": {"Repair", "Routine Maintenance", "Inspection", "Service Request"},
        "stage": {"Triage", "Assigned", "In Progress", "Awaiting Provider", "Awaiting Parts", "Awaiting Approval", "Verification", "Closed"},
        "closure_type": {"Normal", "Duplicate", "Cancelled", "Non-asset Work"},
    }
    for key, choices in options.items():
        if value(doc, key) and value(doc, key) not in choices:
            raise ValueError("Invalid " + key)
    for start, end in (("outage_start", "restored"), ("provider_sent", "provider_completed"),
                       ("failure_date", "restored"), ("restored", "verified")):
        a, b = value(doc, start), value(doc, end)
        if a and b and parse(b) < parse(a):
            raise ValueError(end + " cannot precede " + start)
    if value(doc, "restored") and not value(doc, "outage_start"):
        raise ValueError("Restoration requires an actual outage start")
    if value(doc, "triaged"):
        for key in ("category", "work_type", "owner", "route"):
            if not value(doc, key):
                raise ValueError("Triage requires " + key)
        if value(doc, "route") == "Other Contractor" and not value(doc, "provider"):
            raise ValueError("External provider is required")
        if value(doc, "work_type") == "Repair" and value(doc, "asset") and not ready(doc):
            raise ValueError("Asset repair requires failure date and operating-status acknowledgment")


def closure_error(doc, repair=None, manager=False, duplicate_valid=False):
    if not value(doc, "triaged"):
        return "Confirm triage before resolution"
    kind = value(doc, "closure_type") or "Normal"
    if kind in {"Duplicate", "Cancelled"}:
        if not manager or not value(doc, "closure_reason"):
            return "Internal manager and exception reason required"
        if kind == "Duplicate" and not duplicate_valid:
            return "Select a valid primary ticket"
        return None
    if not value(doc, "verified"):
        return "Internal verification is required"
    if value(doc, "work_type") == "Repair":
        if value(doc, "asset") and not repair:
            return "Link an Asset Repair before resolution"
        if not value(doc, "asset") and (kind != "Non-asset Work" or not value(doc, "closure_reason")):
            return "Identify asset or document Non-asset Work"
    if repair and (repair.get("docstatus") != 1 or repair.get("repair_status") != "Completed"):
        return "Complete and submit the linked Asset Repair"
    if value(doc, "outage_start") and not value(doc, "restored"):
        return "Record actual service restoration"
    return None
