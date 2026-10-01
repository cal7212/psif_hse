"""Starter checklist for the Housekeeping Inspection Template.

Built from the site's existing 'Housekeeping Audit' Quality Inspection
Template, grouped by category, with critical flags and OSHA references.
Load it once from the desk console (or bench console):

	from hse.housekeeping_inspection.setup.default_template import create_default_template
	create_default_template()
"""

import frappe

TEMPLATE_NAME = "Housekeeping - Weekly Area Inspection"
PROCEDURE = "Weekly Housekeeping Audit"

# (category, check item, acceptance criteria, critical, reference)
ITEMS = [
	(
		"Walking-Working Surfaces",
		"Floors clean, dry and free of slip hazards",
		"No oil, water, debris or dust on walking surfaces.",
		0,
		"OSHA 1910.22(a)",
	),
	(
		"Walking-Working Surfaces",
		"Spills contained and absorbent available",
		"No uncontained spills; spill kit or absorbent stocked in the area.",
		0,
		"OSHA 1910.22(a)(2)",
	),
	(
		"Walking-Working Surfaces",
		"Floor openings and holes guarded",
		"Covers or guardrails in place on every floor opening.",
		1,
		"OSHA 1910.28(b)(3)",
	),
	(
		"Walking-Working Surfaces",
		"Stairs lit, treads sound and handrails secure",
		"No damaged or slippery treads; handrails tight.",
		0,
		"OSHA 1910.25",
	),
	(
		"Walking-Working Surfaces",
		"Cords, cables and hoses kept out of walkways",
		"Bundled, routed overhead or covered; no trip hazards.",
		0,
		"OSHA 1910.22(a)",
	),
	(
		"Aisles and Exits",
		"Aisles and passageways clear and at least 3 ft wide",
		"No stored material or equipment in marked aisles.",
		0,
		"OSHA 1910.176(a)",
	),
	(
		"Aisles and Exits",
		"Floor markings visible",
		"Aisle, walkway and hazard-zone lines not faded or missing.",
		0,
		"OSHA 1910.176(a)",
	),
	(
		"Aisles and Exits",
		"Exit routes and exit doors unobstructed and marked",
		"Nothing placed in exit routes, even temporarily; exit signs visible.",
		1,
		"OSHA 1910.37(a)(3)",
	),
	(
		"Aisles and Exits",
		"Evacuation map posted",
		"Current evacuation plan posted and readable.",
		0,
		"OSHA 1910.38",
	),
	(
		"Fire Protection",
		"Fire extinguishers accessible and visible",
		"Mounted, unobstructed, and identified.",
		1,
		"OSHA 1910.157(c)(1)",
	),
	(
		"Fire Protection",
		"Extinguisher monthly inspection tag current",
		"Tag initialed within the last month.",
		0,
		"OSHA 1910.157(e)(2)",
	),
	(
		"Fire Protection",
		"18 in clearance below sprinkler heads",
		"No material stored within 18 in of sprinkler deflectors.",
		1,
		"OSHA 1910.159(c)(10)",
	),
	(
		"Fire Protection",
		"First aid kit and eyewash accessible",
		"Unobstructed and stocked.",
		0,
		"OSHA 1910.151",
	),
	(
		"Electrical",
		"Electrical panels have 3 ft clear working space",
		"Nothing stored in front of panels or disconnects.",
		1,
		"OSHA 1910.303(g)(1)",
	),
	(
		"Material Storage",
		"Materials stacked securely",
		"Stacked, blocked or interlocked and limited in height to prevent sliding or collapse.",
		1,
		"OSHA 1910.176(b)",
	),
	(
		"Material Storage",
		"Heavy items stored on lower shelves",
		"Heavy or bulky items at or below waist height on racks.",
		0,
		"OSHA 1910.176(b)",
	),
	(
		"Material Storage",
		"Storage areas free of clutter and waste",
		"No accumulation creating trip, fire, explosion or pest hazards.",
		0,
		"OSHA 1910.176(c)",
	),
	(
		"Material Storage",
		"Personal items stored in designated areas",
		"Jackets, bags and lunch boxes in lockers or break areas.",
		0,
		"",
	),
	(
		"Chemicals and Flammables",
		"Flammable liquids stored properly",
		"In approved containers or flammable cabinets; limits not exceeded.",
		1,
		"OSHA 1910.106(e)(2)",
	),
	(
		"Chemicals and Flammables",
		"Secondary containers labeled",
		"Every secondary container has a GHS workplace label.",
		0,
		"OSHA 1910.1200(f)(6)",
	),
	(
		"Waste and Sanitation",
		"Enough waste containers, including for hazardous waste",
		"Separate bins for flammable or hazardous waste where needed.",
		0,
		"OSHA 1910.141(a)(4)",
	),
	(
		"Waste and Sanitation",
		"Waste containers emptied, not overflowing",
		"No overflowing bins.",
		0,
		"OSHA 1910.141(a)(4)",
	),
	(
		"Waste and Sanitation",
		"Oily rags in self-closing metal containers",
		"Approved, lidded metal cans; lids closed.",
		1,
		"NFPA 1 (Fire Code)",
	),
	(
		"Waste and Sanitation",
		"Restrooms and break areas clean and sanitary",
		"Clean, stocked, and in working order.",
		0,
		"OSHA 1910.141(a)(3)",
	),
]

INSTRUCTIONS = (
	"<p>Walk the whole area, including corners, behind racks and exterior doors.</p>"
	"<ul><li>Mark each item Pass, Fail or N/A.</li>"
	"<li>For every Fail, describe what you found and where. Attach a photo when you can.</li>"
	"<li>If you fix the condition during the walk (for example, move a pallet out of an exit route), "
	"tick <b>Corrected on the Spot</b>. Critical items that are not corrected raise a Critical Non Conformance.</li>"
	"<li>Sign and submit before leaving the area.</li></ul>"
)


def create_default_template(procedure: str = PROCEDURE, passing_score: float = 90):
	if frappe.db.exists("Housekeeping Inspection Template", TEMPLATE_NAME):
		return TEMPLATE_NAME
	doc = frappe.get_doc(
		{
			"doctype": "Housekeeping Inspection Template",
			"template_name": TEMPLATE_NAME,
			"quality_procedure": procedure,
			"passing_score": passing_score,
			"instructions": INSTRUCTIONS,
			"items": [
				{"category": c, "check_item": i, "criteria": cr, "is_critical": crit, "reference": ref}
				for c, i, cr, crit, ref in ITEMS
			],
		}
	)
	doc.insert()
	return doc.name
