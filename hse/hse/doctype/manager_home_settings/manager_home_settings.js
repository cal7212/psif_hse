// Manager Home Settings: who opens the Executive Dashboard after login (hse.hse.manager_home).
frappe.ui.form.on("Manager Home Settings", {
	refresh(frm) {
		frm.fields_dict.preview_html.$wrapper.html(
			`<p class="text-muted small">${__(
				"Save first, then click the button to list the users the saved rules produce."
			)}</p>`
		);
	},
	show_users(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Save the settings first. The list uses the saved rules."));
			return;
		}
		frappe.call("hse.hse.manager_home.preview").then((r) => {
			const d = r.message || {};
			const esc = frappe.utils.escape_html;
			const rows = (d.users || [])
				.map(
					(u) => `<tr><td>${esc(u.full_name || u.user)}</td><td>${esc(u.user)}</td>
					<td>${esc(u.reasons.join(", "))}</td></tr>`
				)
				.join("");
			const head = d.enabled
				? __("{0} users land on {1}.", [(d.users || []).length, esc(d.home_page)])
				: __("Disabled. Nobody is redirected. With the current rules it would be:");
			const excluded = (d.excluded || []).length
				? `<p class="text-muted small">${__("Excluded")}: ${esc(
						d.excluded.join(", ")
				  )}</p>`
				: "";
			frm.fields_dict.preview_html.$wrapper.html(`<p>${head}</p>
				<table class="table table-sm table-bordered"><thead><tr><th>${__("Name")}</th>
				<th>${__("User")}</th><th>${__("Why")}</th></tr></thead><tbody>${
				rows || `<tr><td colspan="3">${__("Nobody")}</td></tr>`
			}</tbody></table>${excluded}`);
		});
	},
});
