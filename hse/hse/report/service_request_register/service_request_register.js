frappe.query_reports["Service Request Register"] = {
    filters: [
        {fieldname: "from_date", label: __("From Date"), fieldtype: "Date", default: frappe.datetime.month_start(), reqd: 1},
        {fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1},
        {fieldname: "category", label: __("Category"), fieldtype: "Select", options: "\nBuilding Maintenance\nIT\nEquipment Maintenance"},
        {fieldname: "route", label: __("Route"), fieldtype: "Select", options: "\nInternal\nOnsite\nOther Contractor"},
        {fieldname: "provider", label: __("Provider"), fieldtype: "Data"},
        {fieldname: "asset", label: __("Asset"), fieldtype: "Link", options: "Asset"}
    ]
};
