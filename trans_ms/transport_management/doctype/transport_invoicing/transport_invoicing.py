# Copyright (c) 2025, Aakvatech Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate
from trans_ms.utlis.dimension import set_dimension
from erpnext import get_default_company, get_default_currency

class TransportInvoicing(Document):
    
	def before_submit(self):
		items = self.vehicle_trips
		for itm in items:
			vehicle_trip = frappe.get_doc("Vehicle Trip", itm.vehicle_trip)
			if vehicle_trip.sales_invoice:
				frappe.throw("<b>Failed. Vehicle trip {0} has already been invoiced!</b>".format(vehicle_trip.name))
	def on_submit(self):
		create_sales_invoice(self)
		
	def on_cancel(self):
		items = self.vehicle_trips
		for itm in items:
			vehicle_trip = frappe.get_doc("Vehicle Trip", itm.vehicle_trip)
			vehicle_trip.sales_invoice = None
			vehicle_trip.save(ignore_permissions=True)
    
	@frappe.whitelist()
	def get_transport_trip(self):
		#Validations
		if not self.customer:
			frappe.throw(_("Please select Customer first"),title=_("Customer Required"))

		""" Pull trips which are submitted based on criteria selected"""
		submitted_si = transport_trip(self)

		if submitted_si:
			self.set('vehicle_trips', submitted_si)
			frappe.msgprint(_("Vehicle trips generation completed"),title=_("Vehicle trips generation"))
		else:
			frappe.msgprint(_("Sales Vehicle trips are not available for the customer"))

def transport_trip(self):
	final_items = []
	items = frappe.db.sql("""SELECT 
																			
								name, vehicle, custom_shipping_address,	driver, trailer, custom_loaded_quantity, custom_parent_trip
							FROM 
								(`tabVehicle Trip`)
							
							WHERE
								sales_invoice is null and customer = '{0}'
						""".format(self.customer), as_dict=1)
	for itm in items:
		vehicle_trip = itm
		if vehicle_trip.custom_parent_trip:
			final_items.append(frappe._dict({
				'vehicle_trip': itm.name,
				'vehicle': vehicle_trip.vehicle,
				'shipping_address': vehicle_trip.custom_shipping_address,
				'driver': vehicle_trip.driver,
				'trailer': vehicle_trip.trailer,
				'quantity': vehicle_trip.custom_loaded_quantity,
			}))
		else:
			_child_doce = frappe.db.get_value('Vehicle Trip', {'custom_parent_trip': vehicle_trip.name}, ['name', 'custom_loaded_quantity'], as_dict=1)
			if not _child_doce:
				final_items.append(frappe._dict({
					'vehicle_trip': itm.name,
					'vehicle': vehicle_trip.vehicle,
					'shipping_address': vehicle_trip.custom_shipping_address,
					'driver': vehicle_trip.driver,
					'trailer': vehicle_trip.trailer,
					'quantity': vehicle_trip.custom_loaded_quantity,
				}))

	return final_items

 
def get_trip_rate(name):
    doc = frappe.get_doc("Vehicle Trip", name)
    if doc.reference_doctype:
        assignment = frappe.get_doc(doc.reference_doctype, doc.reference_docname)
        return assignment.rate
    elif doc.custom_parent_trip:
        ptrip = frappe.get_doc("Vehicle Trip", doc.custom_parent_trip)
        if ptrip.reference_doctype:
            assignment = frappe.get_doc(ptrip.reference_doctype, ptrip.reference_docname)
            return assignment.rate
            
    return 0
def create_sales_invoice(doc):
	xitems = doc.vehicle_trips
	
	items = []
	item_row_per = []
	company = get_default_company()
	currency = get_default_currency()
	company_abbr = frappe.db.get_value(
		"Company",
		company,
		"abbr",
	)
	for row in xitems:
		# description = ""
		transport_item = frappe.get_value("Transport Settings", None, "transport_item")
		# if row["assigned_vehicle"]:
		#     description += "<b>" + row["assigned_vehicle"] + "/"+row["assigned_trailer"]+"<b>"
		# if row["route"]:
		#     description += "<BR>ROUTE: " + row["route"]
		qty = row.quantity
		rate = get_trip_rate(row.vehicle_trip)
		item = frappe._dict({
				"item_code": transport_item,
				"qty": qty,
				"uom": frappe.get_value("Item", transport_item, "stock_uom"),
				"rate": rate,
				"weight_per_unit": qty,
				"reference_dt": "Vehicle Trip",
				"reference_dn": row.vehicle_trip,
				"cost_center": row.vehicle + " - " + company_abbr,
				"description": transport_item if transport_item else "Transport AGO DPT",
			}
		)
		item_row_per.append([row, item])
		items.append(item)
	invoice = frappe.get_doc(
		dict(
			doctype="Sales Invoice",
			customer=doc.customer,
			currency=currency,
			posting_date=nowdate(),
			company=company,
			items=items,
		),
	)

	set_dimension(doc, invoice, src_child=row)
	for i in item_row_per:
		set_dimension(doc, invoice, src_child=i[0], tr_child=i[1])

	frappe.flags.ignore_account_permission = True
	invoice.set_taxes()
	invoice.set_missing_values()
	invoice.flags.ignore_mandatory = True
	invoice.calculate_taxes_and_totals()
	invoice.insert(ignore_permissions=True)
	invoice.submit()
	for item in doc.vehicle_trips:
		frappe.set_value("Vehicle Trip", item.vehicle_trip, "sales_invoice", invoice.name)
	frappe.msgprint(_("Success. The customer has been invoiced!"))
	return invoice

