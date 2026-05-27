# Copyright (c) 2026, Quantbit Technologies Pvt Ltd
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class BillingRole(Document):

    def on_trash(self):
        
        # if self.name == "User Role":
        #     frappe.throw("Default role 'User Role' cannot be deleted.")
        
        linked_packages = frappe.get_all("Billing Package", filters={"billing_role": self.name})

        for package in linked_packages:
    
            frappe.db.set_value("Billing Package", package.name, "billing_role", None)
            

        if self.billing_role:
            frappe.db.delete("DocPerm", {"role": self.billing_role})
            
            frappe.db.delete("Custom DocPerm", {"role": self.billing_role})

            if frappe.db.exists("Role", self.billing_role):
                frappe.delete_doc(
                    "Role",
                    self.billing_role,
                    ignore_permissions=True,
                    force=1 
                )

    def before_save(self):

        if frappe.flags.in_migrate or frappe.flags.in_import:
            return

        # if self.name == "User Role":
        #     frappe.throw("user role cannot be updated.")

        if not self.billing_role:
            frappe.throw("Enter billing role you want to create.")
        
        if frappe.db.exists("Role", {"role_name": self.billing_role}):
            role = frappe.get_doc("Role", self.billing_role)
            role.role_name = self.billing_role
            role.desk_access = getattr(self, "desk_access", 0)
            role.disabled = getattr(self, "disabled", 0)
            role.save(ignore_permissions=True) 
        else:
            role = frappe.get_doc({
                "doctype": "Role",
                "role_name": self.billing_role,
                "desk_access": getattr(self, "desk_access", 0),
                "disabled": getattr(self, "disabled", 0),
            })
            role.insert(ignore_permissions=True)
        
        self.role = self.billing_role