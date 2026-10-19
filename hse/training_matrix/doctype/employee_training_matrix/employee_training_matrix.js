// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const TM_STATUS_COLORS = {
	Completed: "green",
	"In Progress": "blue",
	Due: "orange",
	Overdue: "red",
	"Not Started": "gray",
	"Confirm Applicability": "purple",
	"Not Applicable": "light-gray",
};

frappe.ui.form.on("Employee Training Matrix", {
	setup(frm) {
		frm.set_indicator_formatter(
			"training_requirement",
			(doc) => TM_STATUS_COLORS[doc.status] || "gray"
		);
	},

	refresh(frm) {
		if (frm.is_new()) return;
		if (!frm.doc.active) {
			frm.dashboard.set_headline_alert(
				__("Employee is not active. The matrix is kept for the record."),
				"gray"
			);
		} else if (frm.doc.overdue_count) {
			frm.dashboard.set_headline_alert(
				__(
					"{0} required course(s) overdue. Escalate to the Manager and HR Manager (TRN-700 §4.9).",
					[frm.doc.overdue_count]
				),
				"red"
			);
		} else if (frm.doc.confirm_count) {
			frm.dashboard.set_headline_alert(
				__("{0} conditional course(s) need the Manager to confirm whether they apply.", [
					frm.doc.confirm_count,
				]),
				"purple"
			);
		}
		if (frm.doc.no_lms_login) {
			frm.dashboard.add_comment(
				__("This employee has no user login, so training cannot be completed in the LMS."),
				"orange",
				true
			);
		}
		if (frappe.user.has_role(["System Manager", "HR Manager", "Training Coordinator"])) {
			frm.add_custom_button(__("Sync from HR"), () =>
				frappe
					.call({
						method: "hse.training_matrix.matrix.sync_employee_matrix",
						args: { employee: frm.doc.employee },
						freeze: true,
					})
					.then(() => frm.reload_doc())
			);
		}
		frm.add_custom_button(__("Training Matrix Report"), () =>
			frappe.set_route("query-report", "Training Matrix", { employee: frm.doc.employee })
		);
		tm_manager_buttons(frm);
	},
});

const TM_SKILLS = "hse.training_matrix.skills";

function tm_manager_buttons(frm) {
	// managers act on their team, never on their own matrix (the server checks this too)
	if (!frm.doc.active || frm.doc.user_id === frappe.session.user) return;
	const group = __("Manager");
	const ready = (frm.doc.skills || []).filter((s) => s.status === "Ready for Authorization");
	ready.forEach((s) =>
		frm.add_custom_button(
			__("Authorize {0}", [s.skill]),
			() =>
				frappe.new_doc("Skill Authorization", {
					employee: frm.doc.employee,
					skill: s.skill,
				}),
			group
		)
	);
	frm.add_custom_button(
		__("Set Target Skill"),
		() =>
			frappe.prompt(
				[
					{
						fieldname: "skill",
						label: __("Skill"),
						fieldtype: "Link",
						options: "Skill Definition",
						reqd: 1,
					},
					{
						fieldname: "due_date",
						label: __("Target Date"),
						fieldtype: "Date",
						reqd: 1,
					},
					{ fieldname: "notes", label: __("Notes"), fieldtype: "Small Text" },
				],
				(values) =>
					frappe
						.call(`${TM_SKILLS}.set_target_skill`, {
							employee: frm.doc.employee,
							...values,
						})
						.then(() => frm.reload_doc()),
				__("Development target")
			),
		group
	);
	if ((frm.doc.target_skills || []).length) {
		frm.add_custom_button(
			__("Remove Target Skill"),
			() =>
				frappe.prompt(
					{
						fieldname: "skill",
						label: __("Skill"),
						fieldtype: "Select",
						options: frm.doc.target_skills.map((t) => t.skill),
						reqd: 1,
					},
					(values) =>
						frappe
							.call(`${TM_SKILLS}.remove_target_skill`, {
								employee: frm.doc.employee,
								skill: values.skill,
							})
							.then(() => frm.reload_doc())
				),
			group
		);
	}
	const conditional = (frm.doc.items || []).filter((r) => r.status === "Confirm Applicability");
	if (conditional.length) {
		frm.add_custom_button(
			__("Confirm Conditional Courses"),
			() =>
				frappe.prompt(
					[
						{
							fieldname: "training_requirement",
							label: __("Course"),
							fieldtype: "Select",
							options: conditional.map((r) => r.training_requirement),
							reqd: 1,
						},
						{
							fieldname: "applicability",
							label: __("Does the task or hazard apply?"),
							fieldtype: "Select",
							options: "Applies\nNot Applicable",
							reqd: 1,
						},
					],
					(values) =>
						frappe
							.call(`${TM_SKILLS}.set_applicability`, {
								employee: frm.doc.employee,
								...values,
							})
							.then(() => frm.reload_doc()),
					__("Conditional course")
				),
			group
		);
	}
}
