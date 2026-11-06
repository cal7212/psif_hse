# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Weekly and monthly Safety, Training and Quality snapshot emails.

- Weekly: every Monday at the send hour (HSE Snapshot Settings, default 8:00 AM America/New_York)
  for the prior Monday to Sunday.
- Monthly: the first Monday of the month at the same time, for the prior calendar month.
- Two versions: Totals (no names, work orders or record numbers) and Internal (adds them).
  Internal recipients must be enabled system users.
- Each send stores an HSE Snapshot with the metric values, so current-status ("now") figures can
  be compared with the previous snapshot of the same frequency.

The job runs every 10 minutes and checks the time in the settings time zone itself, so the send
time does not depend on the site time zone. The content is built as Administrator so scheduled
and manual sends show the same figures; only System Managers can change recipients or send.
"""

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import frappe
from frappe import _
from frappe.utils import add_months, get_first_day, get_last_day, get_url, getdate, now_datetime

from hse.hse.page.executive_dashboard import executive_dashboard as ex
from hse.hse.page.hse_home import hse_home as hh
from hse.quality_metrics.metrics import METRICS, calculate
from hse.shop_qc.page.shop_qc_home import shop_qc_home as qc
from hse.training_matrix.page.training_dashboard import training_dashboard as td

SETTINGS = "HSE Snapshot Settings"
SNAPSHOT = "HSE Snapshot"
WEEKLY, MONTHLY = "Weekly", "Monthly"
TOTALS, INTERNAL = "Totals", "Internal"
TEMPLATE = "hse/templates/emails/hse_snapshot.html"
DEFAULT_TZ = "America/New_York"
TZ_LABELS = {
	"America/New_York": "Eastern",
	"America/Chicago": "Central",
	"America/Denver": "Mountain",
	"America/Phoenix": "Arizona",
	"America/Los_Angeles": "Pacific",
}

SCORECARD = [
	(
		"Safety",
		[
			"recordable_cases",
			"incidents_reported",
			"near_miss_reports",
			"incident_actions_overdue",
			"asset_inspection_on_time_pct",
			"assets_out_of_service",
			"hk_avg_score",
			"hk_areas_overdue",
		],
	),
	(
		"Training",
		[
			"training_compliance_pct",
			"training_overdue",
			"training_high_hazard_overdue",
			"training_due_30",
			"skill_maps_at_risk",
			"skill_authorizations_expiring",
		],
	),
	(
		"Quality",
		[
			"hpu_first_pass_yield",
			"hpu_units_released",
			"rework_opened",
			"nc_opened",
			"capa_overdue",
			"capa_closed_on_time_pct",
		],
	),
]

STATUS_COLORS = {
	"ok": ("#1e7a46", "#e7f5ec"),
	"watch": ("#a15c00", "#fff3e0"),
	"action": ("#b42318", "#fdecea"),
}


def status_badge(key: str) -> tuple[str, str, str]:
	labels = {"ok": _("On track"), "watch": _("Watch"), "action": _("Action needed")}
	return (labels[key], *STATUS_COLORS[key])


DASH = "\u2013"
CLOSED_NC = ["Closed", "Resolved", "Cancelled"]


# --------------------------------------------------------------------------- time
def settings():
	return frappe.get_single(SETTINGS)


def local_now(tz: str | None = None) -> datetime:
	return datetime.now(ZoneInfo(tz or DEFAULT_TZ))


def period_for(frequency: str, on: date) -> tuple[date, date]:
	"""The last complete week (Monday to Sunday) or calendar month before `on`."""
	on = getdate(on)
	if frequency == WEEKLY:
		monday = on - timedelta(days=on.weekday())
		return monday - timedelta(days=7), monday - timedelta(days=1)
	start = getdate(get_first_day(add_months(on, -1)))
	return start, getdate(get_last_day(start))


def previous_period(frequency: str, start: date) -> tuple[date, date]:
	if frequency == WEEKLY:
		return start - timedelta(days=7), start - timedelta(days=1)
	prev = getdate(get_first_day(add_months(start, -1)))
	return prev, getdate(get_last_day(prev))


def is_first_monday(d: date) -> bool:
	return d.weekday() == 0 and d.day <= 7


def fmt_date(d) -> str:
	return frappe.format(getdate(d), "Date")


# --------------------------------------------------------------------------- figures
def fmt(value, uom) -> str:
	if value is None:
		return DASH
	if uom == "Percent":
		return f"{value:.1f}%"
	return f"{value:g}" if isinstance(value, int | float) else str(value)


def change_text(value, prev, uom) -> str | None:
	if value is None or prev is None:
		return None
	diff = value - prev
	if diff == 0:
		return _("no change")
	return f"{diff:+.1f} pts" if uom == "Percent" else f"{diff:+g}"


def last_snapshot(frequency: str, before: date):
	rows = frappe.get_all(
		SNAPSHOT,
		filters={"frequency": frequency, "status": "Sent", "period_start": ["<", str(before)]},
		fields=["name", "values_json"],
		order_by="period_start desc",
		limit=1,
	)
	return rows[0] if rows else None


def scorecard(frequency: str, start: date, end: date) -> tuple[list[dict], dict]:
	"""Groups for the email and the {metric: value} dict stored on the snapshot."""
	pstart, pend = previous_period(frequency, start)
	last = last_snapshot(frequency, start)
	stored = json.loads(last.values_json or "{}") if last else {}
	values: dict = {}
	groups = []
	for g in hh.metric_groups(start, end, SCORECARD):
		rows = []
		for i in g["items"]:
			values[i["key"]] = i["value"]
			if i["snapshot"]:
				prev = stored.get(i["key"]) if last else None
				prev_text = fmt(prev, i["uom"]) if last else _("first snapshot")
			else:
				prev = calculate(i["key"], pstart, pend)[0]
				prev_text = fmt(prev, i["uom"])
			rows.append(
				{
					"label": i["label"] + (" " + _("(now)") if i["snapshot"] else ""),
					"value": fmt(i["value"], i["uom"]),
					"prev": prev_text,
					"first": i["snapshot"] and not last,
					"change": change_text(i["value"], prev, i["uom"]),
					"target": i["target"],
					"status": i["status"],
				}
			)
		groups.append({"group": g["group"], "rows": rows})
	return groups, values


def _dedupe(detail: str | None) -> str | None:
	if not detail:
		return detail
	return ", ".join(dict.fromkeys(detail.split(", ")))


def pillars(start, end) -> tuple[list[dict], dict]:
	safety_att = ex._attention(ex.SAFETY_ATTENTION)
	quality_att = ex._attention(ex.QUALITY_ATTENTION, None)
	training = hh._safe(td.pillar) or {"summary": {}, "attention": []}
	s = hh._safe(hh.safety_summary) or {}
	t = training["summary"] or {}
	steps = {
		x["status"]: x["count"] for x in (hh._safe(qc.pipeline, None, start, end) or {}).get("steps", [])
	}
	cards = [
		{
			"title": _("Safety"),
			"status": status_badge(ex.pillar_status(safety_att)),
			"kpis": [
				(s.get("days_since_recordable", DASH), _("days since last recordable")),
				(s.get("open_reports", 0), _("open incident reports")),
				(s.get("actions_overdue", 0), _("corrective actions overdue")),
			],
			"url": get_url("/app/hse-dashboard"),
		},
		{
			"title": _("Training"),
			"status": status_badge(ex.pillar_status(training["attention"])),
			"kpis": [
				(fmt(t.get("training_compliance_pct"), "Percent"), _("required items Qualified")),
				(t.get("training_overdue", 0), _("items overdue")),
				(t.get("skill_maps_at_risk", 0), _("skill maps at risk")),
			],
			"url": get_url("/app/training-dashboard"),
		},
		{
			"title": _("Quality"),
			"status": status_badge(ex.pillar_status(quality_att)),
			"kpis": [
				(steps.get("QC Hold", 0), _("units on QC Hold")),
				(steps.get("In Build", 0), _("units in build")),
				(steps.get("Ready for Release", 0), _("ready for release")),
			],
			"url": get_url("/app/shop-qc-home"),
		},
	]
	attention = {
		_("Safety"): safety_att,
		_("Training"): training["attention"],
		_("Quality"): quality_att,
	}
	return cards, attention


def attention_rows(attention: dict, internal: bool) -> dict:
	return {
		area: [
			{
				"label": a["label"],
				"count": a["count"],
				"level": a["level"],
				"detail": _dedupe(a.get("detail")) if internal else None,
			}
			for a in items
		]
		for area, items in attention.items()
	}


def _list(doctype, **kw):
	if not frappe.db.table_exists(doctype):
		return []
	return frappe.get_all(doctype, limit=kw.pop("limit", 50), **kw)


def internal_lists(start, end) -> dict:
	span = [str(start), f"{end} 23:59:59"]
	ctx = hh._safe(td.context, 30) or {}
	late = hh._safe(qc.att_late, None)
	return {
		"incidents": _list(
			"Injury_Illness Report",
			filters={"incident_date": ["between", [str(start), str(end)]], "docstatus": ["!=", 2]},
			fields=["name", "incident_date", "type_of_incident", "status", "is_recordable"],
			order_by="incident_date asc",
		),
		"behind": (ctx.get("employees") or [])[:5],
		"skills": (ctx.get("skills") or {}).get("rows", []),
		"due": (ctx.get("coming_due") or [])[:15],
		"open_nc": _list(
			"Nonconformance Report",
			filters={"status": ["not in", CLOSED_NC], "docstatus": ["!=", 2]},
			fields=["name", "record_type", "ncr_no", "capa_no", "capa_status", "subject"],
			order_by="creation asc",
		),
		"hold": _list(
			"QC Unit",
			filters={"status": "QC Hold"},
			fields=["name", "trulinx_work_order", "shop", "product_type"],
			order_by="modified asc",
		),
		"released": _list(
			"QC Unit",
			filters={"released_on": ["between", span]},
			fields=["name", "trulinx_work_order", "shop", "released_on"],
			order_by="released_on asc",
		),
		"late": _dedupe(late.get("detail")) if late and late.get("count") else None,
	}


# --------------------------------------------------------------------------- build
def build(frequency: str, on: date, tz: str, sent_at: datetime | None = None) -> dict:
	"""Everything both versions need, computed once as Administrator."""
	start, end = period_for(frequency, on)
	user = frappe.session.user
	# Fixed report content, same for scheduled and manual sends; only System Managers can send.
	frappe.set_user("Administrator")  # nosemgrep
	try:
		groups, values = scorecard(frequency, start, end)
		cards, attention = pillars(start, end)
		lists = internal_lists(start, end)
		reviews = hh._safe(hh.latest_reviews) if frequency == MONTHLY else []
	finally:
		frappe.set_user(user)  # nosemgrep
	pstart, _pend = previous_period(frequency, start)
	sent_at = sent_at or local_now(tz)
	zone = TZ_LABELS.get(tz, tz)
	if frequency == WEEKLY:
		title = _("Weekly Safety, Training and Quality Snapshot")
		period = _("Week of Mon {0} to Sun {1}").format(fmt_date(start), fmt_date(end))
		prev_label, prev_ref = _("Prior week"), _("the prior week")
	else:
		title = _("Monthly Safety, Training and Quality Snapshot")
		period = _("{0} ({1} to {2})").format(start.strftime("%B %Y"), fmt_date(start), fmt_date(end))
		prev_label = prev_ref = pstart.strftime("%B")
	return {
		"frequency": frequency,
		"start": start,
		"end": end,
		"values": values,
		"title": title,
		"period": period,
		"prev_label": prev_label,
		"prev_ref": prev_ref,
		"sent": _("Sent {0}, {1} {2}").format(
			sent_at.strftime("%A ") + fmt_date(sent_at.date()),
			sent_at.strftime("%I:%M %p").lstrip("0"),
			zone,
		),
		"scorecard": groups,
		"pillars": cards,
		"attention": attention,
		"lists": lists,
		"reviews": reviews or [],
	}


def render(data: dict, version: str) -> str:
	internal = version == INTERNAL
	ctx = dict(data)
	ctx.update(
		internal=internal,
		version=_("Internal: names and record numbers") if internal else _("Totals only"),
		attention=attention_rows(data["attention"], internal),
		lists=data["lists"] if internal else None,
	)
	# TEMPLATE is the app's own file, not user input.
	return frappe.render_template(TEMPLATE, ctx)  # nosemgrep


def subject(data: dict, version: str) -> str:
	s = _("{0}: {1} to {2}").format(data["title"], fmt_date(data["start"]), fmt_date(data["end"]))
	return s + (" " + _("(Internal)") if version == INTERNAL else "")


def pdf_attachment(html: str, data: dict, version: str) -> dict | None:
	try:
		from frappe.utils.pdf import get_pdf

		page = (
			'<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
			'<body style="margin:0;background:#ffffff;">' + html + "</body></html>"
		)
		content = get_pdf(page, {"page-size": "Letter", "margin-top": "8mm", "margin-bottom": "8mm"})
	except Exception:
		frappe.log_error(title=_("HSE Snapshot PDF failed"))
		return None
	name = "{0}-snapshot-{1}-{2}.pdf".format(data["frequency"].lower(), data["start"], version.lower())
	return {"fname": name, "fcontent": content}


def recipients(frequency: str, doc=None) -> dict[str, list[str]]:
	doc = doc or settings()
	flag = "weekly" if frequency == WEEKLY else "monthly"
	out: dict[str, list[str]] = {TOTALS: [], INTERNAL: []}
	for r in doc.recipients or []:
		if r.get(flag) and r.email:
			out[r.version or TOTALS].append(r.email)
	return {k: sorted(set(v)) for k, v in out.items()}


def send(frequency: str, on: date | None = None, to: dict | None = None, store: bool = True) -> str | None:
	"""Build and send one frequency. `to` overrides the recipient lists ({version: [emails]}).
	Returns the HSE Snapshot name when stored."""
	doc = settings()
	tz = doc.time_zone or DEFAULT_TZ
	now = local_now(tz)
	data = build(frequency, getdate(on or now.date()), tz, now)
	to = to if to is not None else recipients(frequency, doc)
	sent_to = []
	for version in (TOTALS, INTERNAL):
		emails = to.get(version) or []
		if not emails:
			continue
		html = render(data, version)
		attachment = pdf_attachment(html, data, version) if doc.attach_pdf else None
		frappe.sendmail(
			recipients=emails,
			subject=subject(data, version),
			message=html,
			attachments=[attachment] if attachment else None,
			reference_doctype=SETTINGS,
			reference_name=SETTINGS,
		)
		sent_to += [f"{e} ({version})" for e in emails]
	if not store:
		return None
	snap = frappe.get_doc(
		{
			"doctype": SNAPSHOT,
			"frequency": frequency,
			"period_start": data["start"],
			"period_end": data["end"],
			"sent_on": now_datetime(),
			"status": "Sent" if sent_to else "No recipients",
			"recipients": "\n".join(sent_to),
			"values_json": json.dumps(data["values"], indent=1, default=str),
		}
	)
	snap.insert(ignore_permissions=True)
	return snap.name


def already_sent(frequency: str, start: date) -> bool:
	return bool(frappe.db.exists(SNAPSHOT, {"frequency": frequency, "period_start": str(start)}))


def due(doc, now: datetime) -> list[str]:
	"""Frequencies to send at local time `now` (Monday at or after the send hour, not yet sent)."""
	if now.weekday() != 0 or now.hour < (doc.send_hour if doc.send_hour is not None else 8):
		return []
	out = []
	today = now.date()
	if doc.weekly_enabled and not already_sent(WEEKLY, period_for(WEEKLY, today)[0]):
		out.append(WEEKLY)
	if (
		doc.monthly_enabled
		and is_first_monday(today)
		and not already_sent(MONTHLY, period_for(MONTHLY, today)[0])
	):
		out.append(MONTHLY)
	return out


def scheduled() -> None:
	"""Cron every 10 minutes (hooks.py)."""
	if not frappe.db.table_exists(SNAPSHOT):
		return
	doc = settings()
	if not (doc.weekly_enabled or doc.monthly_enabled):
		return
	now = local_now(doc.time_zone or DEFAULT_TZ)
	for frequency in due(doc, now):
		# Commit each frequency so one failure does not undo the other.
		try:
			send(frequency, now.date())
			frappe.db.commit()  # nosemgrep
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=_("HSE Snapshot {0} failed").format(frequency))


# --------------------------------------------------------------------------- form actions
def _check(frequency, version=None):
	frappe.only_for("System Manager")
	if frequency not in (WEEKLY, MONTHLY):
		frappe.throw(_("Choose Weekly or Monthly."))
	if version and version not in (TOTALS, INTERNAL):
		frappe.throw(_("Choose Totals or Internal."))


@frappe.whitelist()
def preview(frequency: str = WEEKLY, version: str = TOTALS) -> str:
	"""HTML for the last complete period, nothing sent or stored."""
	_check(frequency, version)
	tz = settings().time_zone or DEFAULT_TZ
	now = local_now(tz)
	return render(build(frequency, now.date(), tz, now), version)


@frappe.whitelist()
def send_now(frequency: str = WEEKLY, to: str = "me", version: str = TOTALS) -> str:
	"""to="me": a test copy of one version to the signed-in user, not stored.
	to="recipients": the normal send to the list, stored like a scheduled send (the scheduled
	job then skips that period)."""
	_check(frequency, version)
	if to == "recipients":
		name = send(frequency)
		return _("Sent and stored as {0}.").format(name)
	email = frappe.db.get_value("User", frappe.session.user, "email")
	if not email:
		frappe.throw(_("Your user has no email address."))
	send(frequency, to={version: [email]}, store=False)
	return _("Test copy sent to {0}.").format(email)
