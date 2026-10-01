"""Pre-Departure and Post-Return housekeeping checklists for job trailers
(As Needed areas). Housekeeping only: road-worthiness (hitch, chains,
lights, tires, brakes) belongs in an Asset Inspection on the trailer asset.

	from hse.housekeeping_inspection.setup.trailer_templates import create_trailer_templates
	create_trailer_templates()
"""

import frappe

PROCEDURE = "Job Trailer Housekeeping Check"
PRE = "Trailer - Pre-Departure"
POST = "Trailer - Post-Return"

PROCEDURE_STEPS = [
	"Before the trailer leaves for a job, open the Trailer area and create a Pre-Departure inspection. Enter the job number in Job / Trip Reference.",
	"Walk the whole trailer interior and exterior storage. Check that tools, materials and equipment are secured for travel and that the floor and aisle are clear.",
	"Confirm the fire extinguisher, first aid kit and spill kit are present, and that chemicals are capped, labeled and stowed.",
	"Correct anything you can on the spot; record anything you cannot. Do not dispatch the trailer with an open critical finding.",
	"When the trailer returns, create a Post-Return inspection with the same Job / Trip Reference.",
	"Remove trash and job debris, clean up spills, dispose of oily rags, note damage, and restock supplies used on the job.",
	"Sign and submit. The area shows Awaiting Return until the Post-Return inspection is submitted.",
]

PRE_ITEMS = [
	(
		"Material Storage",
		"Tools and equipment secured for travel",
		"Strapped, binned or locked in place; nothing can shift or fall in transit.",
		1,
		"",
	),
	(
		"Material Storage",
		"Materials and stock stacked and restrained",
		"Stacks stable, blocked or tied down; heavy items low.",
		1,
		"OSHA 1910.176(b)",
	),
	(
		"Walking-Working Surfaces",
		"Floor and aisle clear",
		"No loose parts, cords, hoses or debris on the floor; clear path to the door.",
		0,
		"OSHA 1910.22(a)",
	),
	(
		"Walking-Working Surfaces",
		"Floor dry and free of oil or fluid",
		"No spills or slick spots.",
		0,
		"OSHA 1910.22(a)",
	),
	(
		"Aisles and Exits",
		"Door and steps clear and working",
		"Door opens fully and latches; steps and grab handles clear.",
		0,
		"",
	),
	(
		"Fire Protection",
		"Fire extinguisher present, charged and secured",
		"Mounted in its bracket, gauge in green, tag current.",
		1,
		"OSHA 1910.157(c)(1)",
	),
	(
		"Fire Protection",
		"First aid kit present and stocked",
		"Kit on board and not depleted.",
		0,
		"OSHA 1910.151(b)",
	),
	(
		"Chemicals and Flammables",
		"Chemicals and fuel capped, labeled and stowed",
		"Approved containers, lids tight, GHS labels, secured upright.",
		1,
		"OSHA 1910.1200(f)(6)",
	),
	(
		"Chemicals and Flammables",
		"Spill kit on board",
		"Absorbent and bags available for the chemicals carried.",
		0,
		"",
	),
	(
		"Electrical",
		"Cords and leads coiled and stowed",
		"No damaged cords; nothing stowed against electrical panels or batteries.",
		0,
		"",
	),
	(
		"General",
		"Job-specific tools, PPE and SDS on board",
		"Items on the job list are loaded; SDS available for chemicals carried.",
		0,
		"OSHA 1910.1200(g)(8)",
	),
]

POST_ITEMS = [
	(
		"Waste and Sanitation",
		"Trash and job debris removed",
		"No packaging, scrap or food waste left in the trailer.",
		0,
		"OSHA 1910.141(a)(4)",
	),
	(
		"Walking-Working Surfaces",
		"Spills and leaks cleaned up",
		"No oil, hydraulic fluid or chemical residue on the floor or shelves.",
		1,
		"OSHA 1910.22(a)",
	),
	(
		"Waste and Sanitation",
		"Oily rags removed or in a self-closing metal can",
		"No loose oily rags left on board.",
		1,
		"NFPA 1 (Fire Code)",
	),
	(
		"Chemicals and Flammables",
		"Chemical and fuel containers capped and stowed",
		"Partially used containers closed, labeled and secured.",
		1,
		"OSHA 1910.1200(f)(6)",
	),
	(
		"Material Storage",
		"Tools and equipment returned to their places",
		"Shelves and bins orderly; nothing left loose.",
		0,
		"OSHA 1910.176(c)",
	),
	(
		"Walking-Working Surfaces",
		"Floor and aisle clear",
		"Clear path to the door; no trip hazards.",
		0,
		"OSHA 1910.22(a)",
	),
	(
		"Tools and Equipment",
		"Damaged tools or equipment tagged and reported",
		"Damaged items tagged out and noted in Findings.",
		0,
		"",
	),
	(
		"Fire Protection",
		"Fire extinguisher still charged and in its bracket",
		"Not used or discharged; report it if it was.",
		1,
		"OSHA 1910.157(c)(1)",
	),
	(
		"Fire Protection",
		"First aid and spill kit restocked",
		"Items used on the job replaced or requested.",
		0,
		"OSHA 1910.151(b)",
	),
	(
		"General",
		"Trailer interior damage noted",
		"New damage to walls, floor, shelving or door recorded with a photo.",
		0,
		"",
	),
]

INSTRUCTIONS = (
	"<p>Use <b>Pre-Departure</b> before the trailer leaves for a job and <b>Post-Return</b> when it comes back. "
	"Enter the job number in Job / Trip Reference on both.</p>"
	"<p>Fix what you can and tick <b>Corrected on the Spot</b>. Do not dispatch the trailer with an open critical finding.</p>"
)


def _template(name, items):
	if frappe.db.exists("Housekeeping Inspection Template", name):
		return name
	frappe.get_doc(
		{
			"doctype": "Housekeeping Inspection Template",
			"template_name": name,
			"quality_procedure": PROCEDURE,
			"passing_score": 90,
			"instructions": INSTRUCTIONS,
			"items": [
				{"category": c, "check_item": i, "criteria": cr, "is_critical": k, "reference": r}
				for c, i, cr, k, r in items
			],
		}
	).insert()
	return name


def create_trailer_templates():
	if not frappe.db.exists("Quality Procedure", PROCEDURE):
		frappe.get_doc(
			{
				"doctype": "Quality Procedure",
				"quality_procedure_name": PROCEDURE,
				"processes": [{"process_description": step} for step in PROCEDURE_STEPS],
			}
		).insert()
	return _template(PRE, PRE_ITEMS), _template(POST, POST_ITEMS)
