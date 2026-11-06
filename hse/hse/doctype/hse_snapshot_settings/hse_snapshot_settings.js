// Copyright (c) 2026, Calvin Johnston and contributors
// For license information, please see license.txt

const SNAP = "hse.hse.snapshot";

function snapshot_dialog(frm, action) {
	const fields = [
		{
			fieldname: "frequency",
			fieldtype: "Select",
			label: __("Frequency"),
			options: "Weekly\nMonthly",
			default: "Weekly",
			reqd: 1,
		},
	];
	if (action !== "recipients") {
		fields.push({
			fieldname: "version",
			fieldtype: "Select",
			label: __("Version"),
			options: "Totals\nInternal",
			default: "Totals",
			reqd: 1,
		});
	}
	const titles = {
		preview: __("Preview snapshot"),
		me: __("Send test copy to me"),
		recipients: __("Send now to recipients"),
	};
	const d = new frappe.ui.Dialog({
		title: titles[action],
		fields: fields,
		primary_action_label: action === "preview" ? __("Preview") : __("Send"),
		primary_action(values) {
			d.hide();
			if (action === "preview") {
				frappe
					.call({ method: `${SNAP}.preview`, args: values, freeze: true })
					.then((r) => show_preview(r.message));
				return;
			}
			const run = () =>
				frappe
					.call({
						method: `${SNAP}.send_now`,
						args: Object.assign({ to: action }, values),
						freeze: true,
						freeze_message: __("Building snapshot..."),
					})
					.then((r) => frappe.msgprint(r.message));
			if (action === "recipients") {
				frappe.confirm(
					__(
						"Send the {0} snapshot for the last complete period to everyone on the list now? It is stored, so the scheduled send skips that period.",
						[__(values.frequency)]
					),
					run
				);
			} else {
				run();
			}
		},
	});
	d.show();
}

function show_preview(html) {
	const d = new frappe.ui.Dialog({ title: __("Snapshot preview"), size: "extra-large" });
	const iframe = document.createElement("iframe");
	iframe.style.cssText = "width:100%;height:75vh;border:0;";
	iframe.srcdoc = html;
	d.$body.empty().append(iframe);
	d.show();
}

frappe.ui.form.on("HSE Snapshot Settings", {
	refresh(frm) {
		frm.add_custom_button(
			__("Preview"),
			() => snapshot_dialog(frm, "preview"),
			__("Snapshot")
		);
		frm.add_custom_button(
			__("Send test copy to me"),
			() => snapshot_dialog(frm, "me"),
			__("Snapshot")
		);
		frm.add_custom_button(
			__("Send now to recipients"),
			() => snapshot_dialog(frm, "recipients"),
			__("Snapshot")
		);
		frm.add_custom_button(__("Sent snapshots"), () =>
			frappe.set_route("List", "HSE Snapshot")
		);
	},
});
