/* global root_element */
// root_element is provided by the Custom HTML Block widget.
const SQC_COLORS = {
	"Pending Build": "gray",
	"In Build": "blue",
	"QC Hold": "red",
	"Ready for Release": "orange",
};
const sqc_rows = root_element.querySelector(".sqc-rows");
const sqc_esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));

frappe
	.xcall("hse.shop_qc.dashboard.active_units")
	.then((units) => {
		if (!units || !units.length) {
			sqc_rows.innerHTML = `<div class="sqc-empty">${__("No active QC Units.")}</div>`;
			return;
		}
		sqc_rows.innerHTML = units
			.map((u) => {
				const color = SQC_COLORS[u.status] || "gray";
				const href = `/app/qc-unit/${encodeURIComponent(u.name)}`;
				return `<a class="sqc-row" href="${href}" data-name="${sqc_esc(u.name)}">
					<span class="sqc-wo">${sqc_esc(u.name)}</span>
					<span class="sqc-muted" title="${sqc_esc(u.model)}">${sqc_esc(u.model)}</span>
					<span class="sqc-muted">${sqc_esc(u.next_stage || __("All stages accepted"))}</span>
					<span class="sqc-pill sqc-${color}">${sqc_esc(__(u.status))}</span>
				</a>`;
			})
			.join("");
	})
	.catch(() => {
		sqc_rows.innerHTML = `<div class="sqc-empty">${__("Could not load QC Units.")}</div>`;
	});

// Route inside the desk instead of reloading the page (the shadow root hides links from the router).
root_element.addEventListener("click", (e) => {
	const row = e.target.closest(".sqc-row");
	const all = e.target.closest(".sqc-all");
	if (!row && !all) return;
	if (e.ctrlKey || e.metaKey || e.shiftKey) return;
	e.preventDefault();
	if (row) frappe.set_route("Form", "QC Unit", row.dataset.name);
	else frappe.set_route("query-report", "QC Unit Build Status");
});
