from collections import Counter
from datetime import timedelta
import frappe
from frappe.utils import get_datetime, now_datetime, add_days
from hse.service_requests.events import enabled, agent
from hse.service_requests.rules import P


def execute(filters=None):
    if not enabled() or not agent():
        frappe.throw("Internal service agent access required", frappe.PermissionError)
    filters = frappe._dict(filters or {})
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw("Select both From Date and To Date")
    if get_datetime(filters.from_date) > get_datetime(filters.to_date):
        frappe.throw("From Date cannot exceed To Date")
    conditions = {P + "category": ["!=", ""], "creation": ["between", [filters.from_date,
                  get_datetime(add_days(filters.to_date, 1)) - timedelta(microseconds=1)]]}
    for key in ("category", "route", "provider", "asset"):
        if filters.get(key):
            conditions[P + key] = filters[key]
    keys = ("category", "owner", "asset", "route", "provider", "repair", "stage", "closure_type",
            "outage_start", "restored", "provider_sent", "provider_completed", "provider_due")
    rows = frappe.get_list("HD Ticket", filters=conditions, fields=["name", "subject", "status", "creation"] +
                           [P + key for key in keys], order_by="creation desc", limit_page_length=10001)
    if len(rows) > 10000:
        frappe.throw("Narrow filters to 10,000 tickets or fewer")
    for row in rows:
        for start, end, target in (("outage_start", "restored", "downtime_hours"),
                                   ("provider_sent", "provider_completed", "provider_hours")):
            a, b = row.get(P + start), row.get(P + end)
            row[target] = (get_datetime(b) - get_datetime(a)).total_seconds() / 3600 if a and b else None
        due = row.get(P + "provider_due")
        row["provider_overdue"] = int(bool(due and not row.get(P + "provider_completed") and
                                            row.get(P + "closure_type") not in {"Duplicate", "Cancelled"} and
                                            get_datetime(due) < now_datetime()))
    columns = [{"fieldname": "name", "label": "Ticket", "fieldtype": "Link", "options": "HD Ticket", "width": 100},
               {"fieldname": "subject", "label": "Subject", "fieldtype": "Data", "width": 240},
               {"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 110}]
    for key in keys[:8]:
        columns.append({"fieldname": P + key, "label": key.replace("_", " ").title(), "fieldtype": "Data", "width": 140})
    for key in ("downtime_hours", "provider_hours", "provider_overdue"):
        columns.append({"fieldname": key, "label": key.replace("_", " ").title(), "fieldtype": "Float", "width": 150})
    counts = Counter(row.get(P + "category") for row in rows)
    chart = {"type": "bar", "data": {"labels": list(counts), "datasets": [{"name": "Requests", "values": list(counts.values())}]}}
    summary = [{"label": "Requests", "value": len(rows), "datatype": "Int"},
               {"label": "Distinct Linked Repairs", "value": len({r.get(P + "repair") for r in rows if r.get(P + "repair")}), "datatype": "Int"},
               {"label": "Provider Overdue", "value": sum(r["provider_overdue"] for r in rows), "datatype": "Int"}]
    return columns, rows, "Per-ticket elapsed hours; shared/overlapping outages are not consolidated asset availability.", chart, summary
