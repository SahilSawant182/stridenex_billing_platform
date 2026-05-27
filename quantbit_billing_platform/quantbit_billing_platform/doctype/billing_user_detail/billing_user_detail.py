# Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class BillingUserDetail(Document):
	def on_trash(self):
		frappe.msgprint( f"Billing user entry for {self.email} has been removed. Disabling the user account.")

		if self.email:

			if frappe.db.exists("User", self.email):

				frappe.db.set_value(
					"User",
					self.email,
					"enabled",
					0
				)

				frappe.msgprint(
					f"User {self.email} has been disabled because the billing user entry was removed."
				)
