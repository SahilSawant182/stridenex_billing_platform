# Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BillingPackage(Document):

    def on_trash(self):
        if self.is_user_package:
            frappe.throw("User package cannot be deleted.")


    def before_save(self):

        if frappe.flags.in_migrate or frappe.flags.in_import:
            return

        if not self.is_new() and self.is_user_package:
            frappe.throw("User package cannot be updated.")
        
        # Scope dependency checks to BOTH app and role
        user_package = frappe.db.exists("Billing Package", {
            "app_name": self.app_name,
            "billing_role": self.billing_role,   
            "is_user_package": 1,
        })

        base_package = frappe.db.exists("Billing Package", {
            "app_name": self.app_name,
            "billing_role": self.billing_role,
            "is_base_package": 1,
        })

        if not self.is_user_package and not self.is_base_package:
            if not user_package:
                frappe.throw(f"User package must be created first for app '{self.app_name}' and role '{self.billing_role}'")

            if not base_package:
                frappe.throw(f"Base package must be created first for app '{self.app_name}' and role '{self.billing_role}'")

        # Uniqueness check for User Package per role
        if self.is_user_package:
            existing = frappe.db.exists("Billing Package", {
                "app_name": self.app_name,
                "billing_role": self.billing_role,
                "is_user_package": 1,
                "name": ["!=", self.name]
            })

            if existing:
                frappe.throw(f"User package already exists for app '{self.app_name}' and role '{self.billing_role}'")

        # Uniqueness check for Base Package per role
        if self.is_base_package:
            existing = frappe.db.exists("Billing Package", {
                "app_name": self.app_name,
                "billing_role": self.billing_role,
                "is_base_package": 1,
                "name": ["!=", self.name]
            })

            if existing:
                frappe.throw(f"Base package already exists for app '{self.app_name}' and role '{self.billing_role}'")
        
        if self.is_new():
            if not frappe.db.exists(
                "Billing Email Setting",
                {
                    "doctype_name": "Billing Package",
                }
            ):
                frappe.msgprint(
                    "Package Created. Please set up email settings for Billing Package to receive email notifications.",
                    alert=True
                )


@frappe.whitelist()
def get_doctypes_from_role(role):
    if not role:
        return []

    role_doc = frappe.get_doc("Billing Role", role)

    if not role_doc.module:
        return []

    doctypes = frappe.get_all(
        "DocType",
        filters={
            "module": role_doc.module,
            "istable": 0 
        },
        pluck="name"
    )

    return doctypes

