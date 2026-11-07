// Shop QC Home: unit pipeline, attention list, first-pass yield by stage, recent inspections,
// quality metrics and goals (shop_qc_home.py). Wrapped so its names stay out of the global scope.
(() => {
	frappe.pages["shop-qc-home"].on_page_load = function (wrapper) {
		const page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Shop QC Home"),
			single_column: true,
		});
		wrapper.shop_qc_home = new ShopQCHome(page, wrapper);
	};

	frappe.pages["shop-qc-home"].on_page_show = function (wrapper) {
		const home = wrapper.shop_qc_home;
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

	class ShopQCHome {
		constructor(page, wrapper) {
			this.page = page;
			this.wrapper = wrapper;
			this.period = localStorage.getItem("shop_qc_home_period") || "this_month";
			this.shop = localStorage.getItem("shop_qc_home_shop") || "";
			this.loaded_at = 0;
			this.$body = $('<div class="hse-home"></div>').appendTo(page.body);
			this.page.set_secondary_action(__("Refresh"), () => this.load(), "refresh");
			this.page.add_inner_button(__("Executive Dashboard"), () =>
				frappe.set_route("executive-dashboard")
			);
			this.bind();
			this.render_skeleton();
			this.load();
		}

		load() {
			this.$body.addClass("is-loading");
			return frappe
				.call({
					method: "hse.shop_qc.page.shop_qc_home.shop_qc_home.get_home",
					args: { period: this.period, shop: this.shop || null },
				})
				.then((r) => {
					this.data = r.message || {};
					if (this.shop && this.data.shop !== this.shop) this.shop = "";
					this.loaded_at = Date.now();
					this.render();
				})
				.catch(() => this.render_error())
				.always(() => this.$body.removeClass("is-loading"));
		}

		find_work_order() {
			frappe.prompt(
				{
					fieldname: "work_order",
					fieldtype: "Data",
					label: __("Work order"),
					reqd: 1,
					description: __(
						"TrulinX work order. Parent and installed-in work orders also match."
					),
				},
				(v) =>
					frappe
						.call({
							method: "hse.shop_qc.page.shop_qc_home.shop_qc_home.find_work_order",
							args: { work_order: v.work_order },
						})
						.then((r) => {
							const names = r.message || [];
							if (names.length === 1) {
								frappe.set_route("Form", "QC Unit", names[0]);
							} else if (names.length) {
								this.open_list("QC Unit", { name: ["in", names] });
							} else {
								frappe.msgprint(
									__("No QC Unit found for work order {0}.", [v.work_order])
								);
							}
						}),
				__("Find a work order"),
				__("Find")
			);
		}

		// ------------------------------------------------------------------ quick actions
		actions() {
			const can = (dt) => frappe.model.can_create(dt);
			const read = (dt) => frappe.model.can_read(dt);
			return [
				{
					key: "find",
					label: __("Find a work order"),
					hint: __("Open the unit by TrulinX WO"),
					icon: "search",
					show: read("QC Unit"),
					run: () => this.find_work_order(),
				},
				{
					key: "qc",
					label: __("QC inspection"),
					hint: __("Inspect a unit at a stage"),
					icon: "clipboard",
					show: can("QC Inspection"),
					run: () => frappe.new_doc("QC Inspection"),
				},
				{
					key: "rework",
					label: __("Log Rework"),
					hint: __("Escalate to NCR from the record"),
					icon: "rework",
					show: can("Nonconformance Report"),
					run: () => frappe.new_doc("Nonconformance Report", { record_type: "Rework" }),
				},
				{
					key: "ncr",
					label: __("Raise an NCR"),
					hint: __("NCR number from the internal log"),
					icon: "alert",
					tone: "danger",
					show: can("Nonconformance Report"),
					run: () => frappe.new_doc("Nonconformance Report", { record_type: "NCR" }),
				},
				{
					key: "repair",
					label: __("Repair evaluation"),
					hint: __("Receive an RGA unit"),
					icon: "wrench",
					show: can("QC Unit"),
					run: () => frappe.new_doc("QC Unit", { job_type: "Repair" }),
				},
				{
					key: "status",
					label: __("Build status"),
					hint: __("Every unit and its stages"),
					icon: "list",
					show: read("QC Unit"),
					run: () => frappe.set_route("query-report", "QC Unit Build Status"),
				},
				{
					key: "instrument",
					label: __("Instruments"),
					hint: __("Calibration status"),
					icon: "gauge",
					show: read("Measuring Instrument"),
					run: () => frappe.set_route("List", "Measuring Instrument"),
				},
				{
					key: "hse_dashboard",
					label: __("HSE Dashboard"),
					hint: __("Safety, equipment and training"),
					icon: "home",
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
					title: __("Units and inspections"),
					icon: "clipboard",
					text: __("Work orders, stages and release"),
					links: [
						L(__("QC Units"), "QC Unit"),
						L(__("QC Inspections"), "QC Inspection"),
						R(
							__("Build Status report"),
							"/app/query-report/QC Unit Build Status",
							"QC Unit"
						),
						R(__("Shop QC workspace"), "/app/shop-qc", "QC Unit"),
						L(__("Repairs (RGA)"), "QC Unit", { job_type: "Repair" }),
					],
				},
				{
					title: __("Rework, NCR and CAPA"),
					icon: "rework",
					text: __("Nonconformance and corrective action"),
					links: [
						L(__("Rework"), "Nonconformance Report", { record_type: "Rework" }),
						L(__("NCRs"), "Nonconformance Report", { record_type: "NCR" }),
						L(__("CAPAs"), "Nonconformance Report", { capa_required: 1 }),
						L(__("SCARs"), "Nonconformance Report", { scar_required: 1 }),
						L(__("Quality Actions"), "Quality Action"),
					],
				},
				{
					title: __("Quality goals and reviews"),
					icon: "chart",
					text: __("Monthly targets and results"),
					links: [
						L(__("Quality Goals"), "Quality Goal"),
						L(__("Quality Reviews"), "Quality Review"),
						L(__("Quality Procedures"), "Quality Procedure"),
					],
				},
				{
					title: __("Templates"),
					icon: "list",
					text: __("Checklists, documents and stages"),
					links: [
						L(__("Inspection Templates"), "QC Inspection Template"),
						L(__("Document Templates"), "QC Document Template"),
						L(__("QC Stages"), "QC Stage"),
					],
				},
				{
					title: __("Setup and reference"),
					icon: "gauge",
					text: __("Shops, hoses, causes and instruments"),
					links: [
						L(__("Build Shops"), "Build Shop"),
						L(__("Hose Types"), "Hose Type"),
						L(__("Hose Crimp Specs"), "Hose Crimp Spec"),
						L(__("Failure Causes"), "QC Failure Cause"),
						L(__("Measuring Instruments"), "Measuring Instrument"),
						R(
							__("Instrument Usage report"),
							"/app/query-report/Instrument Usage",
							"Measuring Instrument"
						),
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
			this.$body.html(`
			${this.hero_html(d)}
			${this.section(__("Quick actions"), this.actions_html())}
			<div class="hse-two">
				${this.section(__("Needs attention"), this.attention_html(d.attention || []))}
				${this.section(__("Recent inspections"), this.recent_html(d.recent || [], d.my_drafts || []))}
			</div>
			${
				d.stage_yield
					? this.section(
							__("First-pass yield by stage"),
							this.stage_html(d.stage_yield),
							range
					  )
					: ""
			}
			${
				(d.metrics || []).length
					? this.section(__("Quality metrics"), this.metrics_html(d.metrics), range)
					: ""
			}
			${(d.reviews || []).length ? this.section(__("Quality goals"), this.reviews_html(d.reviews)) : ""}
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
			const shops = (d.shops || []).length
				? `<label class="hse-shop"><span>${__("Shop")}</span>
				<select class="form-control input-sm" data-shop aria-label="${__("Shop")}">
					<option value="">${__("All shops")}</option>
					${d.shops
						.map(
							(s) =>
								`<option value="${esc(s)}" ${s === d.shop ? "selected" : ""}>${esc(
									s
								)}</option>`
						)
						.join("")}
				</select></label>`
				: "";
			return `<div class="hse-hero hse-card">
			<div class="hse-hero-top">
				<div>
					<h2>${esc(greet)}${first ? ", " + esc(first) : ""}</h2>
					<p class="hse-muted">${esc(frappe.datetime.str_to_user(d.today))} · ${
				d.shop ? esc(d.shop) : __("All shops")
			} · ${__("Builds, inspections and quality")}</p>
				</div>
				<div class="hse-filters">${shops}
					<div class="hse-segs" role="group" aria-label="${__("Metric period")}">${periods}</div>
				</div>
			</div>
			${this.pipeline_html(d.pipeline)}
		</div>`;
		}

		pipeline_html(p) {
			if (!p) return "";
			const tone = {
				"QC Hold": "is-bad",
				"Ready for Release": "is-info",
				Released: "is-good",
			};
			return `<div class="hse-pipeline">${p.steps
				.map(
					(s) => `<button type="button" class="hse-step ${tone[s.status] || ""} ${
						s.count ? "" : "is-zero"
					}" data-open-list="QC Unit" data-filters='${esc(JSON.stringify(s.filters))}'>
					<b>${esc(s.count)}</b><span>${esc(s.label)}</span></button>`
				)
				.join("")}</div>`;
		}

		stage_html(rows) {
			if (!rows.length) {
				return `<div class="hse-card hse-empty">${hse_icon("clipboard", 22)}<p>${__(
					"No first inspections in this period."
				)}</p></div>`;
			}
			const cls = (pct) => (pct >= 95 ? "is-good" : pct >= 85 ? "is-warn" : "is-bad");
			let shop = null;
			const body = rows
				.map((r) => {
					const head =
						r.shop !== shop
							? `<div class="hse-stage-shop">${esc(
									r.shop || __("Other stages")
							  )}</div>`
							: "";
					shop = r.shop;
					return `${head}<button type="button" class="hse-stage" data-open-list="QC Inspection"
					data-filters='${esc(
						JSON.stringify({
							stage: r.stage,
							docstatus: 1,
							inspection_date: [
								"between",
								[this.data.period.start, this.data.period.end],
							],
						})
					)}'
					title="${esc(r.rejected.length ? __("Rejected: {0}", [r.rejected.join(", ")]) : "")}">
					<span class="hse-stage-name">${esc(r.stage)}</span>
					<span class="hse-bar"><span class="${cls(r.pct)}" style="width:${Math.max(
						r.pct,
						2
					)}%"></span></span>
					<span class="hse-stage-pct">${esc(this.fmt(r.pct, "Percent"))}</span>
					<span class="hse-stage-n">${esc(r.passed)}/${esc(r.total)}</span>
				</button>`;
				})
				.join("");
			return `<div class="hse-card hse-stages">${body}
			<p class="hse-muted hse-stage-note">${__(
				"First submitted inspection per unit and stage. Click a stage to see its inspections."
			)}</p></div>`;
		}

		recent_html(rows, drafts) {
			if (!rows.length && !drafts.length) {
				return `<div class="hse-card hse-empty">${hse_icon("clipboard", 22)}<p>${__(
					"No inspections yet."
				)}</p></div>`;
			}
			const chip = (s) =>
				`<span class="hse-chip ${
					s === "Accepted" ? "is-good" : s === "Rejected" ? "is-bad" : ""
				}">${esc(__(s || "Pending"))}</span>`;
			const draft_rows = drafts
				.map(
					(
						r
					) => `<button type="button" class="hse-row" data-doctype="QC Inspection" data-open-doc="${esc(
						r.name
					)}">
					<span class="hse-tag is-draft">${__("My draft")}</span>
					<span class="hse-row-text"><b>${esc(r.qc_unit || r.name)}</b>
					<small>${esc(r.stage || "")} · ${esc(frappe.datetime.comment_when(r.modified))}</small></span>
					<span class="hse-row-go">${hse_icon("arrow", 16)}</span>
				</button>`
				)
				.join("");
			const done_rows = rows
				.map(
					(
						r
					) => `<button type="button" class="hse-row" data-doctype="QC Inspection" data-open-doc="${esc(
						r.name
					)}">
					<span class="hse-row-text"><b>${esc(r.qc_unit || r.name)}</b>
					<small>${esc(r.stage || "")}${r.is_reinspection ? " · " + __("re-inspection") : ""}${
						r.inspector_name ? " · " + esc(r.inspector_name) : ""
					}${
						r.inspection_date
							? " · " + esc(frappe.datetime.str_to_user(r.inspection_date))
							: ""
					}</small></span>
					${chip(r.status)}
					<span class="hse-row-go">${hse_icon("arrow", 16)}</span>
				</button>`
				)
				.join("");
			return `<div class="hse-card hse-list">${draft_rows}${done_rows}</div>`;
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
				localStorage.setItem("shop_qc_home_period", me.period);
				me.load();
			});
			this.$body.on("change", "[data-shop]", function () {
				me.shop = $(this).val() || "";
				localStorage.setItem("shop_qc_home_shop", me.shop);
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
				<p>${__("Shop QC Home could not load. Check your connection and try again.")}</p>
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
