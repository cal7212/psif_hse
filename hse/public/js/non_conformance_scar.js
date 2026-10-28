// QM-134 SCAR on Nonconformance Report (loaded alongside non_conformance.js)
frappe.ui.form.on("Nonconformance Report", {
	refresh(frm) {
		if (frm.is_new()) return;
		const supplier_flagged =
			frm.doc.record_type === "Rework"
				? frm.doc.rw_crit_supplier === "Yes"
				: frm.doc.crit_supplier;
		if (!frm.doc.scar_required) {
			if (supplier_flagged) {
				frm.dashboard.set_headline_alert(
					__(
						"The supplier criterion is marked. Tick SCAR Required on the SCAR tab if a SCAR is issued."
					),
					"blue"
				);
			}
			return;
		}

		frm.add_custom_button(
			__("SCAR Report"),
			() => {
				const url =
					"/printview?doctype=" +
					encodeURIComponent(frm.doctype) +
					"&name=" +
					encodeURIComponent(frm.doc.name) +
					"&format=" +
					encodeURIComponent("QM-134 SCAR Report") +
					"&no_letterhead=1&trigger_print=0";
				window.open(url, "_blank");
			},
			__("View")
		);

		const status = frm.doc.scar_status;
		const due = frm.doc.scar_response_due;
		if (["Issued", "Rejected"].includes(status) && due && due < frappe.datetime.get_today()) {
			frm.dashboard.set_headline_alert(
				__("SCAR {0}: the supplier response was due {1}.", [
					frm.doc.scar_no,
					frappe.datetime.str_to_user(due),
				]),
				"orange"
			);
		}
	},

	scar_required(frm) {
		if (!frm.doc.scar_required) return;
		if (!frm.doc.scar_issued_date)
			frm.set_value("scar_issued_date", frappe.datetime.get_today());
		if (!frm.doc.scar_status) frm.set_value("scar_status", "Issued");
	},

	scar_status(frm) {
		const today = frappe.datetime.get_today();
		const stamp = {
			"Response Received": "scar_response_received",
			Rejected: "scar_rejected_date",
			Approved: "scar_approved_date",
		}[frm.doc.scar_status];
		if (stamp && !frm.doc[stamp]) frm.set_value(stamp, today);
	},
});
