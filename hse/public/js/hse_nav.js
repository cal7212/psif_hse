// HSE navigation, loaded on every desk page (hooks.py app_include_js).
// 1. A "Dashboards" menu in each page header, linking to every dashboard the user can open.
// 2. A "Back to <dashboard>" button on lists, forms and reports opened from a dashboard.
//    The origin dashboard is kept in sessionStorage (per browser tab) and cleared when the
//    user moves to another page or workspace.
// 3. Managers (Manager Home Settings, boot.hse_manager_home) who open the /desk apps screen go
//    to their home page, once per browser tab. Login itself is handled in manager_home.py.
(() => {
	const DASHBOARDS = [
		{ page: "executive-dashboard", label: "Executive Dashboard" },
		{ page: "hse-dashboard", label: "HSE Dashboard" },
		{ page: "training-dashboard", label: "Training Dashboard" },
		{ page: "shop-qc-home", label: "Shop QC Dashboard" },
		{ page: "maintenance-dashboard", label: "Maintenance Dashboard" },
		{ page: "hse-home", label: "HSE Home" },
	];
	// Routes opened from a dashboard that keep the Back button.
	const RECORD_VIEWS = [
		"List",
		"Form",
		"Report",
		"query-report",
		"print",
		"Tree",
		"dashboard-view",
	];
	const KEY = "hse_nav_origin";

	const esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));

	function allowed() {
		const info = frappe.boot && frappe.boot.page_info;
		if (!info || !Object.keys(info).length) return DASHBOARDS;
		return DASHBOARDS.filter((d) => info[d.page]);
	}

	function by_page(page) {
		return DASHBOARDS.find((d) => d.page === page);
	}

	function track(route) {
		const first = route[0];
		if (by_page(first)) {
			sessionStorage.setItem(KEY, first);
		} else if (!RECORD_VIEWS.includes(first)) {
			sessionStorage.removeItem(KEY);
		}
	}

	function add_styles() {
		if (document.getElementById("hse-nav-style")) return;
		const css = `
		.hse-nav { display: inline-flex; gap: 8px; align-items: center; margin-right: 8px; position: relative; }
		.hse-nav-menu { position: relative; }
		.hse-nav-list { display: none; position: absolute; right: 0; top: calc(100% + 4px); z-index: 1030;
			min-width: 220px; padding: 4px; background: var(--fg-color, #fff);
			border: 1px solid var(--border-color, #e2e2e2); border-radius: var(--border-radius-md, 8px);
			box-shadow: var(--shadow-md, 0 4px 12px rgba(0,0,0,.12)); }
		.hse-nav-menu.is-open .hse-nav-list { display: block; }
		.hse-nav-list a { display: block; padding: 6px 10px; border-radius: 6px; color: var(--text-color);
			white-space: nowrap; text-decoration: none; }
		.hse-nav-list a:hover, .hse-nav-list a:focus { background: var(--fg-hover-color, #f3f3f3); }
		.hse-nav-list a.is-current { font-weight: 600; }
		@media (max-width: 767px) { .hse-nav .hse-nav-text { display: none; } }`;
		$("<style id='hse-nav-style'>").text(css).appendTo("head");
	}

	function render() {
		const wrapper = frappe.container && frappe.container.page;
		if (!wrapper) return;
		const $section = $(wrapper).find(".page-head .standard-items-section").first();
		if (!$section.length) return;
		const route = frappe.get_route() || [];
		const list = allowed();
		$section.find(".hse-nav").remove();
		if (!list.length) return;

		const origin = by_page(sessionStorage.getItem(KEY));
		const show_back = origin && RECORD_VIEWS.includes(route[0]);
		const back = show_back
			? `<button type="button" class="btn btn-default btn-sm hse-nav-back" data-hse-page="${esc(
					origin.page
			  )}" title="${esc(__("Back to {0}", [__(origin.label)]))}">
				${frappe.utils.icon("left", "xs")}
				<span class="hse-nav-text">${esc(__("Back to {0}", [__(origin.label)]))}</span>
			</button>`
			: "";
		const links = list
			.map(
				(d) =>
					`<a href="/app/${esc(d.page)}" data-hse-page="${esc(d.page)}" class="${
						d.page === route[0] ? "is-current" : ""
					}">${esc(__(d.label))}</a>`
			)
			.join("");
		const $nav = $(`<div class="hse-nav">
			${back}
			<div class="hse-nav-menu">
				<button type="button" class="btn btn-default btn-sm hse-nav-toggle" aria-haspopup="true"
					aria-expanded="false" title="${esc(__("Dashboards"))}">
					${frappe.utils.icon("dashboard", "xs")}
					<span class="hse-nav-text">${esc(__("Dashboards"))}</span>
				</button>
				<div class="hse-nav-list" role="menu">${links}</div>
			</div>
		</div>`);
		$section.prepend($nav);
	}

	function bind() {
		$(document).on("click", ".hse-nav [data-hse-page]", function (e) {
			e.preventDefault();
			$(".hse-nav-menu").removeClass("is-open");
			frappe.set_route($(this).attr("data-hse-page"));
		});
		$(document).on("click", ".hse-nav-toggle", function (e) {
			e.stopPropagation();
			const $menu = $(this).closest(".hse-nav-menu");
			const open = !$menu.hasClass("is-open");
			$(".hse-nav-menu").removeClass("is-open");
			$menu.toggleClass("is-open", open);
			$(this).attr("aria-expanded", open);
		});
		$(document).on("click", (e) => {
			if (!$(e.target).closest(".hse-nav-menu").length)
				$(".hse-nav-menu").removeClass("is-open");
		});
		$(document).on("keydown", (e) => {
			if (e.key === "Escape") $(".hse-nav-menu").removeClass("is-open");
		});
	}

	// The /desk apps screen in v16 (also /app with no route).
	function on_apps_screen() {
		const path = window.location.pathname.replace(/\/+$/, "");
		return path === "/desk" || path === "/app";
	}

	function manager_home() {
		const home = frappe.boot && frappe.boot.hse_manager_home;
		if (!home || sessionStorage.getItem("hse_manager_home_done")) return false;
		if (!on_apps_screen()) return false;
		sessionStorage.setItem("hse_manager_home_done", "1");
		const route = home.replace(/^\/(app|desk)\/?/, "");
		if (route) frappe.set_route(route.split("/"));
		else window.location.href = home;
		return true;
	}

	let timer = null;
	function on_change() {
		if (!frappe.get_route) return;
		track(frappe.get_route() || []);
		clearTimeout(timer);
		// The page header is built after the route changes; wait for it.
		timer = setTimeout(render, 250);
	}

	$(document).on("app_ready", () => {
		add_styles();
		bind();
		manager_home();
		$(document).on("page-change", on_change);
		if (frappe.router && frappe.router.on) frappe.router.on("change", on_change);
		on_change();
	});
})();
