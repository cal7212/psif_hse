// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const TM_SETUP = "hse.training_matrix.setup.appendix_a";
const TM_MATRIX = "hse.training_matrix.matrix";

frappe.listview_settings["Training Requirement"] = {
	add_fields: ["disabled", "all_employees", "high_hazard"],
	get_indicator(doc) {
		if (doc.disabled) return [__("Disabled"), "gray", "disabled,=,1"];
		if (doc.high_hazard) return [__("High Hazard"), "orange", "high_hazard,=,1"];
		if (doc.all_employees) return [__("All Employees"), "blue", "all_employees,=,1"];
		return [__("By Role"), "green", "all_employees,=,0"];
	},
	onload(listview) {
		if (!frappe.user.has_role(["System Manager", "HR Manager", "Training Coordinator"]))
			return;
		listview.page.add_inner_button(
			__("Load TRN-700 Appendix A"),
			() =>
				frappe.confirm(
					__(
						"Create the four Training Roles and the HR, Safety and QMS courses from TRN-700 Rev 1 Appendix A? Existing records are not changed."
					),
					() =>
						frappe
							.call({ method: `${TM_SETUP}.load_appendix_a`, freeze: true })
							.then(() => listview.refresh())
				),
			__("Training Matrix")
		);
		listview.page.add_inner_button(
			__("Import LMS History"),
			() => tm_import_lms_history(listview),
			__("Training Matrix")
		);
		listview.page.add_inner_button(
			__("Re-sync All Employees"),
			() => frappe.call(`${TM_MATRIX}.resync_all_matrices`),
			__("Training Matrix")
		);
	},
};

function tm_import_lms_history(listview) {
	const method = "hse.training_matrix.lms_history";
	frappe.call({ method: `${method}.preview_lms_history`, freeze: true }).then(({ message }) => {
		const counts = message.counts || {};
		const ready = counts["Will import"] || 0;
		const esc = frappe.utils.escape_html;
		const summary = Object.keys(counts)
			.map((k) => `<li><b>${esc(String(counts[k]))}</b> ${esc(__(k))}</li>`)
			.join("");
		const rows = (message.rows || [])
			.map(
				(r) => `<tr>
					<td>${esc(r.employee_name || "")}</td>
					<td>${esc(r.training_requirement)}</td>
					<td>${esc(r.issue_date || "")}</td>
					<td>${esc(r.expiry_date || "")}</td>
					<td>${r.score == null ? "" : esc(String(Math.round(r.score))) + "%"}</td>
					<td>${esc(__(r.action))}</td>
				</tr>`
			)
			.join("");
		const dialog = new frappe.ui.Dialog({
			title: __("Import LMS History"),
			size: "extra-large",
			fields: [
				{
					fieldtype: "HTML",
					options: rows
						? `<p>${__(
								"LMS certificates held by active employees, for courses linked to a Training Requirement. Each one marked Will import becomes a TRN-702 record dated its issue date."
						  )}</p>
						<ul>${summary}</ul>
						<div style="max-height: 420px; overflow: auto">
							<table class="table table-bordered table-condensed">
								<thead><tr>
									<th>${__("Employee")}</th><th>${__("Course")}</th><th>${__("Issued")}</th>
									<th>${__("Expires")}</th><th>${__("Lowest Quiz")}</th><th>${__("Action")}</th>
								</tr></thead>
								<tbody>${rows}</tbody>
							</table>
						</div>`
						: `<p>${__(
								"No LMS certificates found for courses linked to a Training Requirement. Set the LMS Course on the Training Requirements first."
						  )}</p>`,
				},
			],
			primary_action_label: __("Import {0} Record(s)", [ready]),
			primary_action() {
				dialog.hide();
				frappe
					.call({ method: `${method}.import_lms_history`, freeze: true })
					.then(() => listview.refresh());
			},
		});
		if (!ready) dialog.get_primary_btn().prop("disabled", true);
		dialog.show();
	});
}
