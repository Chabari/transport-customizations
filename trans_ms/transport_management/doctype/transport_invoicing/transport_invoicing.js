// Copyright (c) 2025, Aakvatech Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on('Transport Invoicing', {
	// refresh: function(frm) {

	// }
	get_pending_trips: (frm) => {
		frappe.call({
			method: "get_transport_trip",
			doc: frm.doc,
			callback: function (r) {
				refresh_field("vehicle_trips");
			}
		});
		
	},
});
