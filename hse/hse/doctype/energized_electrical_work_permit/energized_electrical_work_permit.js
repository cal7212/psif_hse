// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

frappe.ui.form.on("Energized Electrical Work Permit", {
	setup(frm) {
		frm.set_query("requested_by", () => ({ filters: { status: "Active" } }));
		frm.set_query("employee", "workers", () => ({ filters: { status: "Active" } }));
		frm.set_query("job_hazard_analysis", () => ({ filters: { status: "Active" } }));
	},
	refresh(frm) {
		window.hse.permits.refresh(frm, "Approved", "work_end");
	},
	incident_energy(frm) {
		// Mirrors MAX_INCIDENT_ENERGY in energized_electrical_work_permit.py.
		if (flt(frm.doc.incident_energy) > 40) {
			frappe.msgprint({
				title: __("Incident Energy"),
				message: __(
					"Above 40 cal/cm² energized work is not approved. De-energize the equipment."
				),
				indicator: "red",
			});
		}
	},
	briefing_done(frm) {
		if (frm.doc.briefing_done && !frm.doc.briefing_time) {
			frm.set_value("briefing_time", frappe.datetime.now_datetime());
		}
	},
});
