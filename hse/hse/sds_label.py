# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Data for the GHS label print formats (hse/hse/print_format/ghs_label_2x4 and ghs_label_4x6)."""

import base64
from functools import cache
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import cstr, get_url

GHS_CODES = {f"GHS0{n}" for n in range(1, 10)}

PT_PER_MM = 72 / 25.4
# Arial: average character width and line height as fractions of the font size (kept conservative)
CHAR_W, LINE_H = 0.52, 1.18
# wkhtmltopdf draws small text slightly wider than it measures it; keep a right margin
TEXT_PAD_MIN, TEXT_PAD_RATIO = 1.8, 0.04
PICTO_GAP = 0.6

# Label profiles, dimensions in mm. Header and footer are fixed boxes; the body sits between them.
# "side" puts the pictograms in a column left of the text, "top" puts them in rows above it.
SIZES = {
	"2x4": frappe._dict(
		w=101.6,
		h=50.8,
		pad_x=2.0,
		pad_top=1.6,
		pad_bottom=1.2,
		header_h=8.0,
		footer_h=8.4,
		gap=0.8,
		layout="side",
		# pictogram count -> (columns, size mm); never taller than the body
		grid={1: (1, 16.0), 2: (1, 13.4), 3: (2, 13.4), 4: (2, 13.4), 5: (3, 12.4), 6: (3, 12.4)},
		grid_max=(3, 9.0),
		font_steps=(7.5, 7.0, 6.5, 6.0, 5.5, 5.0, 4.6, 4.2),
		name_steps=((36, 9.0), (46, 7.5), (100, 6.5)),
		name_min=5.5,
		signal_pt=13,
		pref_pt=5.5,
		footer_pt=5.2,
		notice_pt=6.5,
		rule=0.4,
	),
	"4x6": frappe._dict(
		w=101.6,
		h=152.4,
		pad_x=3.0,
		pad_top=3.0,
		pad_bottom=3.0,
		header_h=15.0,
		footer_h=13.0,
		gap=1.5,
		layout="top",
		grid={1: (1, 24.0), 2: (2, 24.0), 3: (3, 24.0), 4: (4, 21.0), 5: (3, 21.0), 6: (3, 21.0)},
		grid_max=(5, 17.0),
		font_steps=(11.0, 10.0, 9.0, 8.5, 8.0, 7.5, 7.0, 6.5, 6.0, 5.5, 5.0),
		name_steps=((28, 15.0), (40, 12.0), (90, 10.0)),
		name_min=8.0,
		signal_pt=24,
		pref_pt=8,
		footer_pt=7.5,
		notice_pt=9,
		rule=0.6,
	),
}


def geometry(size: str) -> frappe._dict:
	geo = frappe._dict(SIZES[size])
	geo.body_top = geo.pad_top + geo.header_h + geo.gap
	geo.body_h = geo.h - geo.body_top - geo.pad_bottom - geo.footer_h - geo.gap
	geo.body_w = geo.w - 2 * geo.pad_x
	return geo


def picto_layout(count: int, geo: frappe._dict) -> tuple[list[dict], float, float]:
	"""Positions (mm, relative to the body) for each pictogram, and the width and height they use."""
	if not count:
		return [], 0.0, 0.0
	cols, size = geo.grid.get(count, geo.grid_max)
	cols = min(cols, count)
	rows = -(-count // cols)
	positions = [
		{"left": (i % cols) * (size + PICTO_GAP), "top": (i // cols) * (size + PICTO_GAP), "size": size}
		for i in range(count)
	]
	return positions, cols * size + (cols - 1) * PICTO_GAP, rows * size + (rows - 1) * PICTO_GAP


def fit_font(
	hazards: list[str], precautions: str, width_mm: float, height_mm: float, steps: tuple
) -> float | None:
	"""Largest font (pt) at which the statements fit the text box, or None if none does."""
	width_pt, height_pt = width_mm * PT_PER_MM, height_mm * PT_PER_MM
	blocks = [*hazards, precautions] if precautions else list(hazards)
	for pt in steps:
		per_line = max(1, int(width_pt / (CHAR_W * pt)))
		needed = sum(-(-len(b) // per_line) for b in blocks) + (0.4 if precautions and hazards else 0)
		if needed * LINE_H * pt <= height_pt:
			return pt
	return None


@cache
def builtin_pictogram(code: str) -> str | None:
	"""UN GHS pictogram packaged with the app, as a data URI so the PDF needs no file access."""
	path = Path(frappe.get_app_path("hse", "public", "images", "ghs", f"{code}.png"))
	if not path.exists():
		return None
	return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def name_font(name: str, geo: frappe._dict) -> float:
	"""Product name size so it fits the header beside the signal word (two lines at most)."""
	for limit, pt in geo.name_steps:
		if len(name) <= limit:
			return pt
	return geo.name_min


def see_sds_text(sds: str) -> str:
	return _("Precautions: see {0}, Section 2, before use. Full label: GHS Label 4x6.").format(sds)


def lines(text: str | None) -> list[str]:
	return [line.strip() for line in cstr(text).replace("\r", "").split("\n") if line.strip()]


def get_ghs_label_data(sds: str, size: str = "2x4") -> frappe._dict:
	"""Label content and layout. On 2x4, statements too long for the label fall back to a
	workplace label (OSHA 1910.1200(f)(6)(ii)) that refers to the SDS for precautionary statements."""
	geo = geometry(size)
	doc = frappe.get_doc("SDS", sds)
	pictograms = []
	for row in doc.pictograms or []:
		p = frappe.get_cached_value("GHS Pictogram", row.pictogram, ["ghs_code", "image"], as_dict=True)
		if not p:
			continue
		code = cstr(p.ghs_code).strip().upper()
		src = builtin_pictogram(code) if code in GHS_CODES else None
		if not src and p.image:
			src = get_url(p.image)
		if src:
			pictograms.append(frappe._dict(name=row.pictogram, code=code, src=src))

	hazards = lines(doc.hazard_statements)
	precautions = lines(doc.get("precautionary_statements"))
	signal = cstr(doc.signal_word).strip()
	hazardous = bool(pictograms or hazards or (signal and signal != "No Signal Word"))

	address = ", ".join(
		x
		for x in (
			cstr(doc.adress_one).strip(),
			cstr(doc.address_two).strip(),
			cstr(doc.manufacturer_city).strip(),
			" ".join(x for x in (cstr(doc.state_province).strip(), cstr(doc.manufacturer_zip).strip()) if x),
			cstr(doc.manufacturer_country).strip(),
		)
		if x
	)

	# OSHA 1910.1200(f)(1): product identifier, signal word, hazard statements, pictograms,
	# precautionary statements, and name, address and phone of the responsible party.
	missing = []
	if not cstr(doc.product_name).strip():
		missing.append(_("Product Name"))
	if not signal:
		missing.append(_("Signal Word (choose No Signal Word if the SDS has none)"))
	if hazardous:
		if not hazards:
			missing.append(_("Hazard Statements"))
		if not precautions:
			missing.append(_("Precautionary Statements"))
		if doc.pictograms and len(pictograms) < len(doc.pictograms):
			missing.append(_("Pictogram image (GHS code missing on a GHS Pictogram record)"))
	if not cstr(doc.manufacturer_name).strip():
		missing.append(_("Manufacturer Name"))
	if not address:
		missing.append(_("Manufacturer Address"))
	if not (cstr(doc.man_phone).strip() or cstr(doc.emergency_phone).strip()):
		missing.append(_("Manufacturer Phone"))

	positions, picto_w, picto_h = picto_layout(len(pictograms), geo)
	for p, pos in zip(pictograms, positions, strict=True):
		p.update(pos)
	if geo.layout == "side":
		text_left, text_top = (picto_w + 1.5 if picto_w else 0.0), 0.0
	else:
		text_left, text_top = 0.0, (picto_h + 2.0 if picto_h else 0.0)
	text_pad = max(TEXT_PAD_MIN, (geo.body_w - text_left) * TEXT_PAD_RATIO)
	text_w = geo.body_w - text_left - text_pad
	text_h = geo.body_h - text_top

	workplace = False
	precaution_text = (_("Precautions:") + " " + " ".join(precautions)) if precautions else ""
	font = (
		fit_font(hazards, precaution_text, text_w, text_h, geo.font_steps) if hazardous else geo.font_steps[0]
	)
	if font is None and size == "2x4" and hazards:
		workplace = True
		precaution_text = see_sds_text(doc.name)
		font = fit_font(hazards, precaution_text, text_w, text_h, geo.font_steps)
	if font is None:
		font = geo.font_steps[-1]
		missing.append(
			_("The hazard statements are too long for a {0} label.").format(size)
			+ " "
			+ (_("Print the GHS Label 4x6 format.") if size == "2x4" else _("Use a larger label."))
		)

	return frappe._dict(
		doc=doc,
		pictograms=pictograms,
		hazards=hazards,
		precautions=precautions,
		workplace=workplace,
		see_sds=see_sds_text(doc.name),
		size=size,
		signal=signal if signal != "No Signal Word" else "",
		hazardous=hazardous,
		address=address,
		missing=missing,
		font_pt=font,
		name_pt=name_font(cstr(doc.product_name), geo),
		text_left=text_left,
		text_top=text_top,
		text_pad=text_pad,
		geo=geo,
	)
