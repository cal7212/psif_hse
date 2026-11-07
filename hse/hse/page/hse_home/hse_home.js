// HSE Home was folded into the HSE Dashboard. This stub keeps /app/hse-home working for old
// bookmarks and email links: it sends the visitor straight on, carrying any route options or
// query string, and makes no data calls. The Python helpers in hse_home.py are shared by the HSE,
// Executive and Training dashboards and stay. The page record is due to be deleted later.
(() => {
	function forward() {
		const query = frappe.utils.get_query_params ? frappe.utils.get_query_params() : {};
		const options = Object.assign({}, query, frappe.route_options || {});
		frappe.route_options = Object.keys(options).length ? options : null;
		frappe.set_route("hse-dashboard");
	}

	frappe.pages["hse-home"].on_page_load = forward;
	frappe.pages["hse-home"].on_page_show = forward;
})();
