// Maintenance Dashboard: the Maintenance pillar page (maintenance_dashboard.py).
// Maintenance tasks overdue and coming due, repairs, equipment out of service, Helpdesk
// maintenance requests, recent maintenance inspections, metrics and goals. Safety inspections
// (Safety Equipment category or a Safety-purpose template) stay on the HSE Dashboard.
(() => {
	frappe.pages["maintenance-dashboard"].on_page_load = function (wrapper) {
		const page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Maintenance Dashboard"),
			single_column: true,
		});
		wrapper.maintenance_dashboard = new MaintenanceDashboard(page, wrapper);
	};

	frappe.pages["maintenance-dashboard"].on_page_show = function (wrapper) {
		const home = wrapper.maintenance_dashboard;
		if (home && Date.now() - home.loaded_at > 60 * 1000) home.load();
	};

	const HSE_ICONS = {
		alert: '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
		clipboard:
			'<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="m9 14 2 2 4-4"/>',
		wrench: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.8-3.8a6 6 0 0 1-7.9 7.9l-6.9 6.9a2.1 2.1 0 0 1-3-3l6.9-6.9a6 6 0 0 1 7.9-7.9z"/>',
		broom: '<path d="m13 11 9-9"/><path d="M14.6 12.6c.8.8.9 2.1.2 3L10 22l-8-8 6.4-4.8c.9-.7 2.2-.6 3 .2z"/><path d="m6.8 10.4 6.8 6.8"/>',
		rework: '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M8 16H3v5"/>',
		box: '<path d="M21 8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7l7 4a2 2 0 0 0 2 0l7-4a2 2 0 0 0 1-1.7z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
		scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><path d="M7 12h10"/>',
		cart: '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2 2h3l2.7 12.4a2 2 0 0 0 2 1.6h9.7a2 2 0 0 0 2-1.6L23 6H6"/>',
		tag: '<path d="M12.6 2.6A2 2 0 0 0 11.2 2H4a2 2 0 0 0-2 2v7.2a2 2 0 0 0 .6 1.4l8.7 8.7a2.4 2.4 0 0 0 3.4 0l6.6-6.6a2.4 2.4 0 0 0 0-3.4z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
		cap: '<path d="M22 10 12 5 2 10l10 5 10-5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/>',
		user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
		shield: '<path d="M20 13c0 5-3.5 7.5-7.7 9a1 1 0 0 1-.6 0C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.2-2.7a1.2 1.2 0 0 1 1.6 0C14.5 3.8 17 5 19 5a1 1 0 0 1 1 1z"/>',
		gauge: '<path d="m12 14 4-4"/><path d="M3.3 19a10 10 0 1 1 17.4 0"/>',
		chart: '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
		flask: '<path d="M9 2v7.5L4.2 18a2 2 0 0 0 1.8 3h12a2 2 0 0 0 1.8-3L15 9.5V2"/><path d="M8.5 2h7"/><path d="M7 16h10"/>',
		refresh:
			'<path d="M21 12a9 9 0 0 0-9-9 9.8 9.8 0 0 0-6.7 2.7L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.8 9.8 0 0 0 6.7-2.7L21 16"/><path d="M16 16h5v5"/>',
		check: '<path d="M20 6 9 17l-5-5"/>',
		arrow: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
		search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
		list: '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/>',
		flag: '<path d="M4 22V4a1 1 0 0 1 .4-.8A6 6 0 0 1 8 2c3 0 5 2 7.7 2a6.6 6.6 0 0 0 3.7-1 .5.5 0 0 1 .6.4V15a1 1 0 0 1-.4.8 6.6 6.6 0 0 1-3.9 1.2c-2.7 0-4.7-2-7.7-2a6 6 0 0 0-3.6 1.2"/>',
		home: '<path d="M3 10 12 3l9 7v10a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
	};

	function hse_icon(name, size) {
		size = size || 20;
		return `<svg class="hse-ico" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${
			HSE_ICONS[name] || ""
		}</svg>`;
	}

	const esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));
	const LOG = "Asset Maintenance Log";

	class MaintenanceDashboard {
		constructor(page, wrapper) {
			this.page = page;
			this.wrapper = wrapper;
			this.period = localStorage.getItem("maintenance_dashboard_period") || "this_month";
			this.loaded_at = 0;
			this.$body = $('<div class="hse-home"></div>').appendTo(page.body);
			this.page.set_secondary_action(__("Refresh"), () => this.load(), "refresh");
			this.page.add_inner_button(__("Executive Dashboard"), () =>
				frappe.set_route("executive-dashboard")
			);
			this.page.add_inner_button(__("HSE Dashboard"), () =>
				frappe.set_route("hse-dashboard")
			);
			this.bind();
			this.render_skeleton();
			this.load();
		}

		load() {
			this.$body.addClass("is-loading");
			return frappe
				.call({
					method: "hse.asset_inspection.page.maintenance_dashboard.maintenance_dashboard.get_dashboard",
					args: { period: this.period },
				})
				.then((r) => {
					this.data = r.message || {};
					this.loaded_at = Date.now();
					this.render();
				})
				.catch(() => this.render_error())
				.always(() => this.$body.removeClass("is-loading"));
		}

		// ------------------------------------------------------------------ quick actions
		actions() {
			const can = (dt) => frappe.model.can_create(dt);
			const read = (dt) => frappe.model.can_read(dt);
			return [
				{
					key: "request",
					label: __("Maintenance request"),
					hint: __("Open a Helpdesk ticket"),
					icon: "flag",
					tone: "danger",
					show: read("HD Ticket"),
					run: () => (window.location.href = "/helpdesk/tickets/new"),
				},
				{
					key: "inspection",
					label: __("Asset inspection"),
					hint: __("Equipment and tools"),
					icon: "wrench",
					show: can("Asset Inspection"),
					run: () => frappe.new_doc("Asset Inspection"),
				},
				{
					key: "repair",
					label: __("Log a repair"),
					hint: __("Asset Repair"),
					icon: "rework",
					show: can("Asset Repair"),
					run: () => frappe.new_doc("Asset Repair"),
				},
				{
					key: "schedule",
					label: __("Maintenance schedule"),
					hint: __("All maintenance tasks"),
					icon: "list",
					show: read(LOG),
					run: () => frappe.set_route("List", LOG),
				},
				{
					key: "hse_dashboard",
					label: __("HSE Dashboard"),
					hint: __("Safety inspections and incidents"),
					icon: "shield",
					show: true,
					run: () => frappe.set_route("hse-dashboard"),
				},
			].filter((a) => a.show);
		}

		// ------------------------------------------------------------------ modules
		modules() {
			const L = (label, doctype, filters) => ({ label, doctype, filters });
			const R = (label, route, doctype) => ({ label, route, doctype });
			return [
				{
					title: __("Equipment"),
					icon: "wrench",
					text: __("Assets and maintenance plans"),
					links: [
						L(__("Assets"), "Asset"),
						L(__("Asset Maintenance"), "Asset Maintenance"),
						L(__("Maintenance schedule"), LOG),
						L(__("Asset Repairs"), "Asset Repair"),
					],
				},
				{
					title: __("Inspections"),
					icon: "clipboard",
					text: __("Inspection records and templates"),
					links: [
						L(__("Asset Inspections"), "Asset Inspection"),
						L(__("Inspection Templates"), "Asset Inspection Template"),
						L(__("Measuring Instruments"), "Measuring Instrument"),
					],
				},
				{
					title: __("Requests"),
					icon: "flag",
					text: __("Helpdesk maintenance tickets"),
					links: [
						R(__("Helpdesk"), "/helpdesk/tickets", "HD Ticket"),
						L(__("HD Tickets"), "HD Ticket"),
					],
				},
				{
					title: __("Goals and reviews"),
					icon: "chart",
					text: __("Targets and monthly results"),
					links: [
						L(__("Quality Goals"), "Quality Goal"),
						L(__("Quality Reviews"), "Quality Review"),
					],
				},
			]
				.map((m) => ({
					...m,
					links: m.links.filter((l) => !l.doctype || frappe.model.can_read(l.doctype)),
				}))
				.filter((m) => m.links.length);
		}

		// ------------------------------------------------------------------ rendering
		render() {
			const d = this.data;
			const range = `<span class="hse-muted">${esc(
				d.period.label
			)} · ${frappe.datetime.str_to_user(d.period.start)} – ${frappe.datetime.str_to_user(
				d.period.end
			)}</span>`;
			const req = d.requests;
			this.$body.html(`
			${this.hero_html(d)}
			${this.section(__("Quick actions"), this.actions_html())}
			<div class="hse-two">
				${this.section(__("Needs attention"), this.attention_html(d.attention || []))}
				${this.section(__("Overdue by category"), this.category_html(d.by_category || []))}
			</div>
			<div class="hse-two">
				${this.section(
					__("Tasks overdue"),
					this.rows_html(d.overdue || [], __("No maintenance tasks overdue."), true)
				)}
				${this.section(
					__("Coming due in 30 days"),
					this.rows_html(d.coming_due || [], __("Nothing due in the next 30 days."))
				)}
			</div>
			<div class="hse-two">
				${this.section(
					__("Repairs"),
					this.rows_html(d.repairs || [], __("No open repairs."), true),
					`<span class="hse-muted">${__("Open, and completed in the period")}</span>`
				)}
				${this.section(
					__("Equipment out of service"),
					this.rows_html(
						d.out_of_service || [],
						__("All equipment is in service."),
						true
					)
				)}
			</div>
			<div class="hse-two">
				${
					req
						? this.section(
								__("Open maintenance requests"),
								this.rows_html(
									req.rows || [],
									__("No open maintenance requests."),
									true
								)
						  )
						: ""
				}
				${this.section(
					__("Recent maintenance inspections"),
					this.rows_html(d.inspections || [], __("No maintenance inspections yet."))
				)}
			</div>
			${
				(d.metrics || []).length
					? this.section(__("Maintenance metrics"), this.metrics_html(d.metrics), range)
					: ""
			}
			${
				(d.reviews || []).length
					? this.section(__("Maintenance goals"), this.reviews_html(d.reviews))
					: ""
			}
			${this.section(__("Modules"), this.modules_html())}
		`);
		}

		hero_html(d) {
			const first = (d.user || "").split(" ")[0];
			const hour = new Date().getHours();
			const greet =
				hour < 12
					? __("Good morning")
					: hour < 17
					? __("Good afternoon")
					: __("Good evening");
			const periods = (d.periods || [])
				.map(
					(p) =>
						`<button type="button" class="hse-seg ${
							p.key === this.period ? "is-active" : ""
						}" data-period="${esc(p.key)}" aria-pressed="${
							p.key === this.period
						}">${esc(p.label)}</button>`
				)
				.join("");
			return `<div class="hse-hero hse-card">
			<div class="hse-hero-top">
				<div>
					<h2>${esc(greet)}${first ? ", " + esc(first) : ""}</h2>
					<p class="hse-muted">${esc(frappe.datetime.str_to_user(d.today))} · ${__(
				"Maintenance tasks, repairs, equipment status and requests"
			)}</p>
				</div>
				<div class="hse-filters">
					<div class="hse-segs" role="group" aria-label="${__("Metric period")}">${periods}</div>
				</div>
			</div>
			${this.headline_html(d.headline || [])}
		</div>`;
		}

		headline_html(steps) {
			if (!steps.length) return "";
			const tone = { good: "is-good", warn: "is-warn", bad: "is-bad" };
			return `<div class="hse-pipeline">${steps
				.map((s) => {
					const value =
						s.value === null || s.value === undefined
							? "–"
							: s.key === "maintenance_on_time_pct"
							? this.fmt(s.value, "Percent")
							: s.value;
					return `<button type="button" class="hse-step ${tone[s.tone] || ""} ${
						s.value ? "" : "is-zero"
					}" data-open-list="${esc(s.doctype)}" data-filters='${esc(
						JSON.stringify(s.filters || {})
					)}' title="${esc(s.detail || "")}">
					<b>${esc(value)}</b><span>${esc(s.label)}</span></button>`;
				})
				.join("")}</div>`;
		}

		category_html(rows) {
			if (!rows.length) {
				return `<div class="hse-card hse-empty is-good">${hse_icon("check", 22)}<p>${__(
					"No maintenance tasks overdue."
				)}</p></div>`;
			}
			const total = rows.reduce((a, r) => a + r.count, 0);
			return `<div class="hse-card hse-stages">${rows
				.map(
					(r) => `<button type="button" class="hse-stage" data-open-list="${LOG}"
				data-filters='${esc(JSON.stringify(r.filters || {}))}'>
				<span class="hse-stage-name">${esc(r.label)}</span>
				<span class="hse-bar"><span class="is-bad" style="width:${Math.max(
					(r.count / total) * 100,
					2
				)}%"></span></span>
				<span class="hse-stage-pct">${esc(r.count)}</span>
				<span class="hse-stage-n"></span>
			</button>`
				)
				.join("")}</div>`;
		}

		rows_html(rows, empty, good_when_empty) {
			if (!rows.length) {
				return `<div class="hse-card hse-empty ${
					good_when_empty ? "is-good" : ""
				}">${hse_icon(good_when_empty ? "check" : "wrench", 22)}<p>${esc(
					empty
				)}</p></div>`;
			}
			const good = ["Completed", "Closed", "Resolved", "Pass", "Passed"];
			const bad = ["Overdue", "Fail", "Failed", "Cancelled", "Safety"];
			const chip = (s) =>
				s
					? `<span class="hse-chip ${
							good.includes(s) ? "is-good" : bad.includes(s) ? "is-bad" : ""
					  }">${esc(__(s))}</span>`
					: "";
			return `<div class="hse-card hse-list">${rows
				.map(
					(r) => `<button type="button" class="hse-row" ${
						r.url
							? `data-open-url="${esc(r.url)}"`
							: `data-doctype="${esc(r.doctype)}" data-open-doc="${esc(r.name)}"`
					}>
					<span class="hse-row-text"><b>${esc(r.title)}</b>
					<small>${esc(r.subtitle || r.name)}${
						r.date ? " · " + esc(frappe.datetime.str_to_user(r.date)) : ""
					}</small></span>
					${chip(r.status)}
					<span class="hse-row-go">${hse_icon("arrow", 16)}</span>
				</button>`
				)
				.join("")}</div>`;
		}

		bind() {
			const me = this;
			this.$body.on("click", "[data-action]", function () {
				me.run_action($(this).attr("data-action"));
			});
			this.$body.on("click", "[data-attention]", function () {
				const item = me.data.attention.find(
					(a) => a.key === $(this).attr("data-attention")
				);
				if (item) me.open_list(item.doctype, item.route_options);
			});
			this.$body.on("click", "[data-open-list]", function (e) {
				e.preventDefault();
				me.open_list(
					$(this).attr("data-open-list"),
					JSON.parse($(this).attr("data-filters") || "{}")
				);
			});
			this.$body.on("click", "[data-open-url]", function () {
				window.location.href = $(this).attr("data-open-url");
			});
			this.$body.on("click", "[data-open-doc]", function () {
				frappe.set_route(
					"Form",
					$(this).attr("data-doctype"),
					$(this).attr("data-open-doc")
				);
			});
			this.$body.on("click", "[data-route]", function (e) {
				const route = $(this).attr("data-route");
				if (route.startsWith("/") && !route.startsWith("/app/")) {
					window.location.href = route;
				} else {
					e.preventDefault();
					frappe.set_route(route.replace(/^\/app\//, "").split("/"));
				}
			});
			this.$body.on("click", "[data-period]", function () {
				me.period = $(this).attr("data-period");
				localStorage.setItem("maintenance_dashboard_period", me.period);
				me.load();
			});
			this.$body.on("click", "[data-metric]", function () {
				$(this).toggleClass("is-open");
				$(this).attr("aria-expanded", $(this).hasClass("is-open"));
			});
		}

		open_list(doctype, filters) {
			frappe.route_options = filters || {};
			frappe.set_route("List", doctype);
		}

		run_action(key) {
			const a = this.actions().find((x) => x.key === key);
			if (a) a.run();
		}

		render_skeleton() {
			const bar = (w) => `<div class="hse-skel" style="width:${w}"></div>`;
			this.$body.html(`
			<div class="hse-hero hse-card">${bar("40%")}${bar("25%")}</div>
			<div class="hse-grid hse-actions">${Array(6)
				.fill(`<div class="hse-card hse-skel-card">${bar("60%")}${bar("40%")}</div>`)
				.join("")}</div>`);
		}

		render_error() {
			this.$body.html(`
			<div class="hse-card hse-empty">
				<p>${__("Maintenance Dashboard could not load. Check your connection and try again.")}</p>
				<button class="btn btn-default btn-sm" data-period="${esc(this.period)}">${__(
				"Try again"
			)}</button>
			</div>`);
		}

		section(title, inner, aside) {
			return `<section class="hse-section">
			<div class="hse-section-head"><h3>${esc(title)}</h3>${aside || ""}</div>
			${inner}
		</section>`;
		}

		actions_html() {
			return `<div class="hse-grid hse-actions">${this.actions()
				.map(
					(a) => `<button type="button" class="hse-card hse-action ${
						a.tone ? "is-" + a.tone : ""
					}" data-action="${a.key}">
					<span class="hse-action-ico">${hse_icon(a.icon, 22)}</span>
					<span class="hse-action-text"><b>${esc(a.label)}</b><small>${esc(a.hint)}</small></span>
				</button>`
				)
				.join("")}</div>`;
		}

		attention_html(items) {
			if (!items.length) {
				return `<div class="hse-card hse-empty is-good">${hse_icon("check", 22)}<p>${__(
					"Nothing needs attention right now."
				)}</p></div>`;
			}
			return `<div class="hse-card hse-list">${items
				.map(
					(a) => `<button type="button" class="hse-row" data-attention="${esc(a.key)}">
					<span class="hse-count is-${esc(a.level)}">${esc(a.count)}</span>
					<span class="hse-row-text"><b>${esc(a.label)}</b>${
						a.detail ? `<small>${esc(a.detail)}</small>` : ""
					}</span>
					<span class="hse-row-go">${hse_icon("arrow", 16)}</span>
				</button>`
				)
				.join("")}</div>`;
		}

		fmt(value, uom) {
			if (value === null || value === undefined) return "–";
			if (uom === "Percent") return `${format_number(value, null, 1)}%`;
			if (uom === "Day") return `${format_number(value, null, 1)} ${__("days")}`;
			return format_number(value, null, Number.isInteger(value) ? 0 : 1);
		}

		metrics_html(groups) {
			const status_chip = (m) => {
				if (!m.target) return `<span class="hse-chip">${__("No target set")}</span>`;
				const cls =
					m.status === "Passed" ? "is-good" : m.status === "Failed" ? "is-bad" : "";
				return `<span class="hse-chip ${cls}">${__("Goal")} ${esc(m.target)}</span>`;
			};
			return groups
				.map(
					(g) => `<div class="hse-metric-group">
				<h4>${esc(g.group)}</h4>
				<div class="hse-grid hse-metrics">${g.items
					.map(
						(m) => `<button type="button" class="hse-card hse-metric ${
							m.status === "Failed"
								? "is-bad"
								: m.status === "Passed"
								? "is-good"
								: ""
						}" data-metric="${esc(m.key)}" aria-expanded="false">
						<span class="hse-metric-label">${esc(m.label)}${
							m.snapshot ? ` <span class="hse-now">${__("now")}</span>` : ""
						}</span>
						<span class="hse-metric-value">${esc(this.fmt(m.value, m.uom))}</span>
						${status_chip(m)}
						<span class="hse-metric-detail">${esc(m.detail || "")}</span>
					</button>`
					)
					.join("")}</div>
			</div>`
				)
				.join("");
		}

		reviews_html(reviews) {
			const badge = (s) => {
				if (!s) return `<span class="hse-chip">${__("No review yet")}</span>`;
				const cls = s === "Passed" ? "is-good" : s === "Failed" ? "is-bad" : "";
				return `<span class="hse-chip ${cls}">${esc(__(s))}</span>`;
			};
			return `<div class="hse-card hse-list">${reviews
				.map(
					(r) => `<button type="button" class="hse-row" data-doctype="${
						r.review ? "Quality Review" : "Quality Goal"
					}"
					data-open-doc="${esc(r.review || r.goal)}">
					<span class="hse-row-text"><b>${esc(r.goal)}</b><small>${
						r.date
							? __("Last review {0}", [frappe.datetime.str_to_user(r.date)])
							: __("First review is created on the goal's review day")
					}</small></span>
					${badge(r.status)}
					<span class="hse-row-go">${hse_icon("arrow", 16)}</span>
				</button>`
				)
				.join("")}</div>`;
		}

		modules_html() {
			return `<div class="hse-grid hse-modules">${this.modules()
				.map(
					(m) => `<div class="hse-card hse-module">
				<div class="hse-module-head"><span class="hse-action-ico">${hse_icon(m.icon, 20)}</span>
					<div><b>${esc(m.title)}</b><small>${esc(m.text)}</small></div></div>
				<ul>${m.links
					.map((l) =>
						l.route
							? `<li><a href="${esc(l.route)}" data-route="${esc(l.route)}">${esc(
									l.label
							  )}</a></li>`
							: `<li><a href="#" data-open-list="${esc(
									l.doctype
							  )}" data-filters='${esc(JSON.stringify(l.filters || {}))}'>${esc(
									l.label
							  )}</a></li>`
					)
					.join("")}</ul>
			</div>`
				)
				.join("")}</div>`;
		}
	}
})();
