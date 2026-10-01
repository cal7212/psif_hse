// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const HK_METHOD =
	"hse.housekeeping_inspection.doctype.housekeeping_inspection.housekeeping_inspection";

frappe.ui.form.on("Housekeeping Area", {
	setup(frm) {
		frm.set_query("template", () => ({ filters: { disabled: 0 } }));
		frm.set_query("post_return_template", () => ({ filters: { disabled: 0 } }));
		frm.set_query("location", () => ({ filters: { is_group: 0 } }));
	},

	periodicity(frm) {
		if (frm.doc.periodicity === "As Needed") frm.set_value("next_due_date", null);
	},

	refresh(frm) {
		if (frm.is_new()) return;

		const as_needed = frm.doc.periodicity === "As Needed";
		if (!frm.doc.disabled) {
			const create = (reason) =>
				frappe.model.open_mapped_doc({
					method: `${HK_METHOD}.make_from_area`,
					frm,
					args: reason ? { reason } : undefined,
				});
			if (as_needed) {
				frm.add_custom_button(
					__("Pre-Departure Inspection"),
					() => create("Pre-Departure"),
					__("Create")
				);
				frm.add_custom_button(
					__("Post-Return Inspection"),
					() => create("Post-Return"),
					__("Create")
				);
			} else {
				frm.add_custom_button(__("Housekeeping Inspection"), () => create(), __("Create"));
			}
			frm.page.set_inner_btn_group_as_primary(__("Create"));
		}
		if (frm.doc.last_inspection) {
			frm.add_custom_button(
				__("Last Inspection"),
				() => {
					frappe.set_route("Form", "Housekeeping Inspection", frm.doc.last_inspection);
				},
				__("View")
			);
		}

		const colors = {
			Satisfactory: "green",
			"Action Required": "orange",
			"Hazard Open": "red",
		};
		if (frm.doc.housekeeping_status) {
			frm.page.set_indicator(
				__(frm.doc.housekeeping_status),
				colors[frm.doc.housekeeping_status] || "gray"
			);
		}
		if (frm.doc.housekeeping_status === "Hazard Open") {
			frm.dashboard.set_headline_alert(
				__(
					"A critical housekeeping hazard is open in this area. See the Non Conformances on the Connections tab."
				),
				"red"
			);
		} else if (as_needed && frm.doc.schedule_status === "Awaiting Return") {
			frm.dashboard.set_headline_alert(
				__("Out on a job. Do the Post-Return inspection when it comes back."),
				"blue"
			);
		} else if (frm.doc.schedule_status === "Overdue") {
			frm.dashboard.set_headline_alert(
				__("Inspection overdue since {0}.", [
					frappe.datetime.str_to_user(frm.doc.next_due_date),
				]),
				"orange"
			);
		}
	},
});
