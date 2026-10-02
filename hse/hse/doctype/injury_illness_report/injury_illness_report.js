// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

// Days away / restricted days, counted per 29 CFR 1904.7(b)(3):
// start the day after the injury, count calendar days up to (not including)
// the return date, cap each table's total at 180. The server recalculates on save.
const DAY_CAP = 180;
const DAY_TABLES = ["days_away", "job_restriction"];

function count_days(row, incident_date) {
	if (!row.start_date || !row.return_date) return 0;
	let start = row.start_date;
	if (incident_date) {
		const day_after = frappe.datetime.add_days(incident_date, 1);
		if (frappe.datetime.get_diff(day_after, start) > 0) start = day_after;
	}
	return Math.max(frappe.datetime.get_diff(row.return_date, start), 0);
}

function recalculate_table(frm, table) {
	let remaining = DAY_CAP;
	(frm.doc[table] || []).forEach((row) => {
		if (row.start_date && row.return_date && frappe.datetime.get_diff(row.return_date, row.start_date) < 0) {
			frappe.msgprint(__("Return Date cannot be before Start Date"));
			return;
		}
		const days = Math.min(count_days(row, frm.doc.incident_date), remaining);
		remaining -= days;
		if (row.number_of_days_away !== days) {
			frappe.model.set_value(row.doctype, row.name, "number_of_days_away", days);
		}
	});
}

function recalculate_all(frm) {
	DAY_TABLES.forEach((table) => recalculate_table(frm, table));
}

frappe.ui.form.on("Injury_Illness Report", {
	incident_date: recalculate_all,
	days_away_remove: (frm) => recalculate_table(frm, "days_away"),
	job_restriction_remove: (frm) => recalculate_table(frm, "job_restriction"),
});

frappe.ui.form.on("Days Away from Work", {
	start_date: (frm, cdt, cdn) => recalculate_table(frm, locals[cdt][cdn].parentfield),
	return_date: (frm, cdt, cdn) => recalculate_table(frm, locals[cdt][cdn].parentfield),
});
