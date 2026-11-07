// Executive Dashboard: one card per pillar (Safety, Training, Quality, Maintenance) with headline numbers and the top
// items needing attention, a metric scorecard and goal status (executive_dashboard.py).
(() => {
	frappe.pages["executive-dashboard"].on_page_load = function (wrapper) {
		const page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Executive Dashboard"),
			single_column: true,
		});
		wrapper.executive_dashboard = new ExecutiveDashboard(page, wrapper);
	};

	frappe.pages["executive-dashboard"].on_page_show = function (wrapper) {
		const home = wrapper.executive_dashboard;
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
		dashboard:
			'<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
	};

	function hse_icon(name, size) {
		size = size || 20;
		return `<svg class="hse-ico" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${
			HSE_ICONS[name] || ""
		}</svg>`;
	}

	const esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));

	class ExecutiveDashboard {
		constructor(page, wrapper) {
			this.page = page;
			this.wrapper = wrapper;
			this.period = localStorage.getItem("executive_dashboard_period") || "this_month";
			this.loaded_at = 0;
			this.$body = $('<div class="hse-home hse-exec"></div>').appendTo(page.body);
			this.page.set_secondary_action(__("Refresh"), () => this.load(), "refresh");
			if (frappe.user.has_role("System Manager")) {
				this.page.add_menu_item(__("Snapshot Emails"), () =>
					frappe.set_route("Form", "HSE Snapshot Settings")
				);
				this.page.add_menu_item(__("Manager Home Page"), () =>
					frappe.set_route("Form", "Manager Home Settings")
				);
			}
			this.bind();
			this.render_skeleton();
			this.load();
		}

		bind() {
			const me = this;
			this.$body.on("click", "[data-attention]", function () {
				const [pillar, key] = $(this).attr("data-attention").split(":");
				const item = ((me.data[pillar] || {}).attention || []).find((a) => a.key === key);
				if (item && item.route) frappe.set_route(item.route);
				else if (item) me.open_list(item.doctype, item.route_options);
			});
			this.$body.on("click", "[data-open-list]", function (e) {
				e.preventDefault();
				me.open_list(
					$(this).attr("data-open-list"),
					JSON.parse($(this).attr("data-filters") || "{}")
				);
			});
			this.$body.on("click", "[data-open-doc]", function () {
				frappe.set_route(
					"Form",
					$(this).attr("data-doctype"),
					$(this).attr("data-open-doc")
				);
			});
			this.$body.on("click", "[data-route]", function (e) {
				e.preventDefault();
				frappe.set_route(
					$(this)
						.attr("data-route")
						.replace(/^\/app\//, "")
						.split("/")
				);
			});
			this.$body.on("click", "[data-period]", function () {
				me.period = $(this).attr("data-period");
				localStorage.setItem("executive_dashboard_period", me.period);
				me.load();
			});
			this.$body.on("click", "[data-metric]", function () {
				$(this).toggleClass("is-open");
				$(this).attr("aria-expanded", $(this).hasClass("is-open"));
			});
		}

		load() {
			this.$body.addClass("is-loading");
			return frappe
				.call({
					method: "hse.hse.page.executive_dashboard.executive_dashboard.get_dashboard",
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

		render_skeleton() {
			const bar = (w) => `<div class="hse-skel" style="width:${w}"></div>`;
			const card = `<div class="hse-card hse-pillar">${bar("40%")}${bar("70%")}${bar(
				"55%"
			)}</div>`;
			this.$body.html(`
			<div class="hse-hero hse-card">${bar("40%")}${bar("25%")}</div>
			<div class="hse-pillars">${card}${card}${card}${card}</div>`);
		}

		render_error() {
			this.$body.html(`
			<div class="hse-card hse-empty">
				<p>${__("The dashboard could not load. Check your connection and try again.")}</p>
				<button class="btn btn-default btn-sm" data-period="${esc(this.period)}">${__(
				"Try again"
			)}</button>
			</div>`);
		}

		render() {
			const d = this.data;
			const range = `<span class="hse-muted">${esc(
				d.period.label
			)} · ${frappe.datetime.str_to_user(d.period.start)} – ${frappe.datetime.str_to_user(
				d.period.end
			)}</span>`;
			this.$body.html(`
			${this.hero_html(d)}
			<div class="hse-pillars">
				${this.safety_html(d)}
				${this.training_html(d)}
				${this.quality_html(d)}
				${this.maintenance_html(d)}
			</div>
			${
				(d.metrics || []).length
					? this.section(__("Scorecard"), this.scorecard_html(d.metrics), range)
					: ""
			}
			${(d.reviews || []).length ? this.section(__("Goals"), this.reviews_html(d.reviews)) : ""}
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
				"Safety, training, quality and maintenance at a glance"
			)}</p>
				</div>
				<div class="hse-segs" role="group" aria-label="${__("Metric period")}">${periods}</div>
			</div>
		</div>`;
		}

		metric(key) {
			for (const g of this.data.metrics || []) {
				const m = g.items.find((x) => x.key === key);
				if (m) return m;
			}
			return null;
		}

		// A KPI tile: {value, label, tone, list: [doctype, filters] | route}
		kpi_html(k) {
			const attrs = k.list
				? `data-open-list="${esc(k.list[0])}" data-filters='${esc(
						JSON.stringify(k.list[1] || {})
				  )}'`
				: `data-route="${esc(k.route)}"`;
			return `<button type="button" class="hse-kpi ${k.tone ? "is-" + k.tone : ""}" ${attrs}>
				<b>${esc(k.value)}</b><span>${esc(k.label)}</span></button>`;
		}

		metric_kpi(key, label, route) {
			const m = this.metric(key);
			if (!m) return null;
			return {
				value: this.fmt(m.value, m.uom),
				label: label,
				tone: m.status === "Failed" ? "bad" : m.status === "Passed" ? "good" : "",
				route: route,
			};
		}

		pillar_html(p) {
			const status = {
				ok: [__("On track"), "is-good"],
				watch: [__("Watch"), "is-warn"],
				action: [__("Action needed"), "is-bad"],
			}[p.status || "ok"];
			const items = p.attention || [];
			const top = items.slice(0, 4);
			const more = items.length - top.length;
			const rows = top.length
				? `<div class="hse-list hse-pillar-list">${top
						.map(
							(a) => `<button type="button" class="hse-row" data-attention="${esc(
								p.key
							)}:${esc(a.key)}">
						<span class="hse-count is-${esc(a.level)}">${esc(a.count)}</span>
						<span class="hse-row-text"><b>${esc(a.label)}</b>${
								a.detail ? `<small>${esc(a.detail)}</small>` : ""
							}</span>
						<span class="hse-row-go">${hse_icon("arrow", 16)}</span>
					</button>`
						)
						.join("")}</div>`
				: `<div class="hse-empty is-good">${hse_icon("check", 22)}<p>${__(
						"Nothing needs attention right now."
				  )}</p></div>`;
			return `<section class="hse-card hse-pillar">
				<div class="hse-pillar-head">
					<span class="hse-action-ico">${hse_icon(p.icon, 22)}</span>
					<div><h3>${esc(p.title)}</h3><small>${esc(p.text)}</small></div>
					<span class="hse-chip ${status[1]}">${esc(status[0])}</span>
				</div>
				<div class="hse-kpis">${p.kpis
					.filter(Boolean)
					.map((k) => this.kpi_html(k))
					.join("")}</div>
				<h4>${__("Needs attention")}</h4>
				${rows}
				<div class="hse-pillar-foot">
					${
						more > 0
							? `<span class="hse-muted">${__("{0} more on the dashboard", [
									more,
							  ])}</span>`
							: "<span></span>"
					}
					<a class="btn btn-primary btn-sm" href="${esc(p.route)}" data-route="${esc(p.route)}">${esc(
				p.open_label
			)} ${hse_icon("arrow", 14)}</a>
				</div>
			</section>`;
		}

		safety_html(d) {
			const p = d.safety || {};
			const s = p.summary;
			const route = "/app/hse-dashboard";
			const kpis = [];
			if (s) {
				const days = s.days_since_recordable;
				kpis.push(
					{
						value: days === null ? "–" : days,
						label:
							days === null
								? __("No recordable incidents on record")
								: __("Days since last recordable"),
						tone: days === null || days >= 30 ? "good" : "warn",
						list: ["Injury_Illness Report", { is_recordable: 1 }],
					},
					{
						value: s.open_reports,
						label: __("Open injury reports"),
						tone: s.open_reports ? "warn" : "",
						list: [
							"Injury_Illness Report",
							{ status: ["in", ["To-Do", "In Progress", "Reopened"]] },
						],
					},
					{
						value: s.actions_overdue,
						label: __("Corrective actions overdue"),
						tone: s.actions_overdue ? "bad" : "",
						list: [
							"Injury_Illness Report",
							{
								date_due: ["between", d.overdue_range],
								date_done: ["is", "not set"],
							},
						],
					}
				);
			}
			kpis.push(
				this.metric_kpi(
					"safety_assets_out_of_service",
					__("Safety equipment out of service"),
					route
				)
			);
			return this.pillar_html({
				key: "safety",
				title: __("Safety"),
				text: __("Incidents, equipment, housekeeping and SDS"),
				icon: "shield",
				route: route,
				open_label: __("Open HSE Dashboard"),
				status: p.status,
				attention: p.attention,
				kpis: kpis,
			});
		}

		training_html(d) {
			const p = d.training;
			if (!p) return "";
			const s = p.summary || {};
			const route = "/app/training-dashboard";
			const pct = s.training_compliance_pct;
			const kpis = [
				{
					value: pct === null || pct === undefined ? "–" : this.fmt(pct, "Percent"),
					label: __("Required items Qualified"),
					tone: pct === 100 ? "good" : pct === null || pct === undefined ? "" : "bad",
					route: route,
				},
				{
					value: s.training_overdue || 0,
					label: __("Required items overdue"),
					tone: s.training_overdue ? "bad" : "",
					list: ["Employee Training Matrix", { overdue_count: [">", 0] }],
				},
				{
					value: s.training_due || 0,
					label: __("Coming due in 30 days"),
					tone: s.training_due ? "warn" : "",
					route: route,
				},
				{
					value: s.skill_maps_at_risk || 0,
					label: __("Skill maps at risk"),
					tone: s.skill_maps_at_risk ? "warn" : "",
					route: route,
				},
			];
			return this.pillar_html({
				key: "training",
				title: __("Training"),
				text: __("Required training, skill maps and authorizations"),
				icon: "cap",
				route: route,
				open_label: __("Open Training Dashboard"),
				status: p.status,
				attention: p.attention,
				kpis: kpis,
			});
		}

		quality_html(d) {
			const p = d.quality || {};
			const route = "/app/shop-qc-home";
			const step = (status) =>
				((p.pipeline || {}).steps || []).find((s) => s.status === status);
			const hold = step("QC Hold");
			const ncr = (p.attention || []).find((a) => a.key === "ncr");
			const kpis = [
				this.metric_kpi("hpu_first_pass_yield", __("First-pass yield"), route),
				hold && {
					value: hold.count,
					label: __("Units on QC Hold"),
					tone: hold.count ? "bad" : "",
					list: ["QC Unit", hold.filters],
				},
				frappe.model.can_read("Nonconformance Report") && {
					value: ncr ? ncr.count : 0,
					label: __("Open NCRs"),
					tone: ncr ? "warn" : "",
					list: ["Nonconformance Report", { record_type: "NCR", status: "Open" }],
				},
				this.metric_kpi("capa_overdue", __("CAPAs overdue"), route),
			];
			return this.pillar_html({
				key: "quality",
				title: __("Quality"),
				text: __("Shop QC builds, inspections, Rework, NCR and CAPA"),
				icon: "clipboard",
				route: route,
				open_label: __("Open Shop QC Home"),
				status: p.status,
				attention: p.attention,
				kpis: kpis,
			});
		}

		maintenance_html(d) {
			const p = d.maintenance;
			if (!p) return "";
			const s = p.summary || {};
			const route = "/app/maintenance-dashboard";
			const pct = s.maintenance_on_time_pct;
			const kpis = [
				{
					value: s.maintenance_overdue || 0,
					label: __("Maintenance tasks overdue"),
					tone: s.maintenance_overdue ? "bad" : "",
					route: route,
				},
				{
					value: pct === null || pct === undefined ? "–" : this.fmt(pct, "Percent"),
					label: __("On time this month"),
					tone: "",
					route: route,
				},
				{
					value: s.out_of_service || 0,
					label: __("Equipment out of service"),
					tone: s.out_of_service ? "bad" : "",
					route: route,
				},
				s.requests_open !== null &&
					s.requests_open !== undefined && {
						value: s.requests_open,
						label: __("Open maintenance requests"),
						tone: s.requests_open ? "warn" : "",
						route: route,
					},
			];
			return this.pillar_html({
				key: "maintenance",
				title: __("Maintenance"),
				text: __("Maintenance tasks, repairs, equipment and requests"),
				icon: "wrench",
				route: route,
				open_label: __("Open Maintenance Dashboard"),
				status: p.status,
				attention: p.attention,
				kpis: kpis,
			});
		}

		scorecard_html(groups) {
			const routes = {
				[__("Safety")]: ["/app/hse-dashboard", __("HSE Dashboard")],
				[__("Training")]: ["/app/training-dashboard", __("Training Dashboard")],
				[__("Quality")]: ["/app/shop-qc-home", __("Shop QC Home")],
				[__("Maintenance")]: ["/app/maintenance-dashboard", __("Maintenance Dashboard")],
			};
			return groups
				.map((g) => {
					const r = routes[g.group];
					const head = r
						? `<div class="hse-group-head"><h4>${esc(g.group)}</h4><a href="${esc(
								r[0]
						  )}" data-route="${esc(r[0])}">${esc(r[1])} ${hse_icon(
								"arrow",
								14
						  )}</a></div>`
						: `<h4>${esc(g.group)}</h4>`;
					return this.metrics_html([g]).replace(`<h4>${esc(g.group)}</h4>`, head);
				})
				.join("");
		}

		open_list(doctype, filters) {
			frappe.route_options = filters || {};
			frappe.set_route("List", doctype);
		}

		section(title, inner, aside) {
			return `<section class="hse-section">
			<div class="hse-section-head"><h3>${esc(title)}</h3>${aside || ""}</div>
			${inner}
		</section>`;
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
	}
})();
