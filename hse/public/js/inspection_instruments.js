// Test equipment on QC Inspection and Asset Inspection (see hse/hse/instruments.py)
const HSE_INSTRUMENT_READING_FIELDS = {
	"QC Inspection": [
		["items", "instrument"],
		["hose_tests", "instrument"],
		["hose_tests", "crimp_instrument"],
		["hose_tests", "particle_counter"],
		["pmg_tests", "instrument"],
		["pmg_tests", "amps_instrument"],
		["accumulator_tests", "instrument"],
		["proof_tests", "instrument"],
	],
	"Asset Inspection": [["items", "instrument"]],
};

function hse_setup_instrument_queries(frm) {
	frm.set_query("instrument", "instruments", () => ({ filters: { status: "Active" } }));
	// Once instruments are listed, a reading can only pick from that list.
	const query = () => {
		const listed = (frm.doc.instruments || []).map((r) => r.instrument).filter(Boolean);
		return listed.length
			? { filters: { name: ["in", listed] } }
			: { filters: { status: "Active" } };
	};
	(HSE_INSTRUMENT_READING_FIELDS[frm.doctype] || []).forEach(([table, field]) =>
		frm.set_query(field, table, query)
	);
}

Object.keys(HSE_INSTRUMENT_READING_FIELDS).forEach((doctype) => {
	frappe.ui.form.on(doctype, { setup: hse_setup_instrument_queries });
});

frappe.ui.form.on("Inspection Instrument", {
	instrument(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.instrument) return;
		frappe.db
			.get_value("Measuring Instrument", row.instrument, [
				"status",
				"calibration_required",
				"calibration_due",
			])
			.then(({ message: m }) => {
				if (!m) return;
				const on = (frm.doc.inspection_date || frappe.datetime.now_datetime()).slice(
					0,
					10
				);
				if (m.status !== "Active") {
					frappe.msgprint(__("{0} is {1}.", [row.instrument, __(m.status)]));
				} else if (m.calibration_required && !m.calibration_due) {
					frappe.msgprint(__("{0} has no calibration due date.", [row.instrument]));
				} else if (
					m.calibration_required &&
					frappe.datetime.get_diff(m.calibration_due, on) < 0
				) {
					frappe.msgprint(
						__("{0} is out of calibration (due {1}).", [
							row.instrument,
							frappe.datetime.str_to_user(m.calibration_due),
						])
					);
				}
			});
	},
});
