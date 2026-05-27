# Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
import pymysql

class BillingModuleConfiguration(Document):
    def on_update(self):

        if frappe.db.exists("Billing Module Configuration", {"app": self.app, "name": ["!=", self.name]}):
            frappe.throw("Another Billing Module Configuration already exists for this app.")

        try:
            self.process_enabled_modules()
        except Exception as e:
            error_msg = str(e)
            doctype = self.extract_doctype_from_error(error_msg)
            
            if doctype:
                frappe.throw(
                    f"<span style='color: red;'>Save failed due to an error in another app/doctype.</span><br><br>"
                    f"<span style='color: #d32f2f;'><b>Doctype:</b> {doctype}</span><br>"
                    f"<span style='color: #d32f2f;'><b>Error:</b> {error_msg}</span><br><br>"
                    f"<span style='color: #ff6b6b;'>Please resolve the issue in the '{doctype}' doctype first, then try saving again.</span>"
                )
            else:
                frappe.throw(
                    f"<span style='color: #ff6b6b;'>Please resolve the issue in the '{doctype}' doctype first then try saving again.</span>"
                )

    def extract_doctype_from_error(self, error_msg):
        import re
        # Match pattern like 'tabJournal Entry.custom_doc_link' or 'tabJournal Entry'
        match = re.search(r"tab([A-Za-z0-9_ ]+)", error_msg)
        if match:
            return match.group(1).strip()
        return None

    def on_trash(self):
        if self.app:
            is_in_use = frappe.db.exists("Active Package Details", {"app_name": self.app})
            
            if is_in_use:
                frappe.throw(("This app cannot be deleted because it is currently assigned to one or more users."))

    def process_enabled_modules(self):
        enabled_modules = [d.module_name for d in self.billing_module_list if d.module_name]
        if not enabled_modules:
            return

        doctypes = frappe.get_all(
            "DocType",
            filters={"module": ["in", enabled_modules], "istable": 0, "issingle": 0},
            fields=["name"]
        )

        for dt in doctypes:
            self.ensure_company_field_exists(dt.name)


    def ensure_company_field_exists(self, doctype_name):
        meta = frappe.get_meta(doctype_name)

        company_field = None

        for field in meta.fields:
            if field.fieldname == "company":
                company_field = field
                break

        if not company_field:
            df = {
                "fieldname": "company",
                "label": "Company",
                "fieldtype": "Link",
                "options": "Company",
                "reqd": 1,
                "print_hide": 1
            }

            create_custom_field(doctype_name, df)
            frappe.msgprint(f"Added Company field to {doctype_name}")

        else:
            if not company_field.reqd:

                custom_field_name = frappe.db.get_value(
                    "Custom Field",
                    {
                        "dt": doctype_name,
                        "fieldname": "company"
                    },
                    "name"
                )

                if custom_field_name:
                    frappe.db.set_value(
                        "Custom Field",
                        custom_field_name,
                        "reqd",
                        1
                    )
                else:
                    frappe.make_property_setter({
                        "doctype": doctype_name,
                        "fieldname": "company",
                        "property": "reqd",
                        "value": "1",
                        "property_type": "Check"
                    })

                frappe.msgprint(f"Updated Company field to mandatory in {doctype_name}")



@frappe.whitelist()
def get_modules_from_app(app_name):
    if not app_name:
        return []

    return frappe.get_all(
        "Module Def",
        filters={"app_name": app_name},
        fields=["name"],
        order_by="name asc"
    )
