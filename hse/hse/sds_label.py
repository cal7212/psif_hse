# Copyright (c) 2026, Calvin Johnston and contributors
# For license information, please see license.txt
"""Data for the GHS 2x4 label print format (hse/hse/print_format/ghs_label_2x4)."""

import base64
from functools import cache
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import cstr, get_url

GHS_CODES = {f"GHS0{n}" for n in range(1, 10)}

# Text size tiers for hazard + precautionary statements on a 4 x 2 in label: (max characters, pt)
FONT_TIERS = ((300, 7.5), (550, 6.6), (850, 5.8), (1050, 5.0), (1250, 4.6))
MIN_FONT_PT = 4.2
MAX_CHARS = 1450  # beyond this the statements will not fit legibly on a 2x4 label


@cache
def builtin_pictogram(code: str) -> str | None:
	"""UN GHS pictogram packaged with the app, as a data URI so the PDF needs no file access."""
	path = Path(frappe.get_app_path("hse", "public", "images", "ghs", f"{code}.png"))
	if not path.exists():
		return None
	return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def picto_size(count: int) -> float:
	"""Diamond size in inches so every pictogram fits the 1.3 in body height."""
	if count <= 2:
		return 0.6
	if count <= 4:
		return 0.5
	if count <= 6:
		return 0.4
	return 0.34


def lines(text: str | None) -> list[str]:
	return [line.strip() for line in cstr(text).replace("\r", "").split("\n") if line.strip()]


def get_ghs_label_data(sds: str) -> frappe._dict:
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

	chars = sum(len(x) for x in hazards + precautions)
	font = next((pt for limit, pt in FONT_TIERS if chars <= limit), MIN_FONT_PT)
	if chars > MAX_CHARS:
		missing.append(
			_(
				"Statements are too long for a 2x4 label ({0} characters, limit {1}). Use a larger label."
			).format(chars, MAX_CHARS)
		)

	return frappe._dict(
		doc=doc,
		pictograms=pictograms,
		hazards=hazards,
		precautions=precautions,
		signal=signal if signal != "No Signal Word" else "",
		hazardous=hazardous,
		address=address,
		missing=missing,
		font_pt=font,
		# pictogram size: fewer pictograms get bigger diamonds
		picto_in=picto_size(len(pictograms)),
		picto_cols=1 if len(pictograms) <= 2 else (2 if len(pictograms) <= 6 else 3),
	)
