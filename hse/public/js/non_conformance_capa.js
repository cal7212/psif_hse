// QM-128 CAPA on Nonconformance Report (loaded alongside non_conformance.js)
(() => {
	// Statuses before each completion date moves the CAPA forward (capa.py apply_completion)
	const BEFORE_CONTAINMENT_DONE = ["Open", "Containment"];
	const BEFORE_CORRECTION_DONE = ["Open", "Containment", "Investigation", "Corrective Action"];

	frappe.ui.form.on("Nonconformance Report", {
		refresh(frm) {
			if (frm.is_new() || !frm.doc.capa_required) return;

			frm.add_custom_button(
				__("CAPA Report"),
				() => {
					const url =
						"/printview?doctype=" +
						encodeURIComponent(frm.doctype) +
						"&name=" +
						encodeURIComponent(frm.doc.name) +
						"&format=" +
						encodeURIComponent("QM-128 CAPA Report") +
						"&no_letterhead=1&trigger_print=0";
					window.open(url, "_blank");
				},
				__("View")
			);

			const status = frm.doc.capa_status;
			if (!status || ["Closed", "Cancelled"].includes(status)) return;
			const today = frappe.datetime.get_today();
			const late = (d) => d && d < today;
			let msg = null;
			if (late(frm.doc.capa_closure_due)) {
				msg = __("CAPA {0} is past its closure due date ({1}).", [
					frm.doc.capa_no,
					frappe.datetime.str_to_user(frm.doc.capa_closure_due),
				]);
			} else if (
				late(frm.doc.capa_correction_due) &&
				!frm.doc.capa_correction_done &&
				BEFORE_CORRECTION_DONE.includes(status)
			) {
				msg = __("CAPA {0} is past its correction due date ({1}).", [
					frm.doc.capa_no,
					frappe.datetime.str_to_user(frm.doc.capa_correction_due),
				]);
			} else if (
				late(frm.doc.capa_containment_due) &&
				!frm.doc.capa_containment_done &&
				BEFORE_CONTAINMENT_DONE.includes(status)
			) {
				msg = __("CAPA {0} containment was due {1}.", [
					frm.doc.capa_no,
					frappe.datetime.str_to_user(frm.doc.capa_containment_due),
				]);
			}
			if (msg) frm.dashboard.set_headline_alert(msg, "orange");
		},

		capa_required(frm) {
			if (frm.doc.capa_required && !frm.doc.capa_initiated_date) {
				frm.set_value("capa_initiated_date", frappe.datetime.get_today());
			}
			if (frm.doc.capa_required && !frm.doc.capa_status)
				frm.set_value("capa_status", "Open");
		},

		capa_containment_done(frm) {
			if (!frm.doc.capa_containment_done) return;
			if (BEFORE_CONTAINMENT_DONE.includes(frm.doc.capa_status)) {
				frm.set_value("capa_status", "Investigation");
			}
		},

		capa_correction_done(frm) {
			if (!frm.doc.capa_correction_done) return;
			if (BEFORE_CORRECTION_DONE.includes(frm.doc.capa_status)) {
				frm.set_value("capa_status", "Verification");
			}
		},

		capa_status(frm) {
			if (frm.doc.capa_status === "Closed" && !frm.doc.capa_closure_date) {
				frm.set_value("capa_closure_date", frappe.datetime.get_today());
			}
		},
	});
})();
