# Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BillingRolePermissionSetting(Document):

    def before_save(self):

        if not self.billing_role:
            return

        required_doctypes = [
            "Billing Account Master",
            "Billing Role",
            "Billing Package",
            "Billing Module Configuration",
            "Billing Notification",
            "Payment Invoice Details"
        ]

        # Collect existing doctypes already present
        existing_doctypes = {row.doctype_name for row in self.doctypes}

        # Add only missing doctypes
        for dt in required_doctypes:

            if dt not in existing_doctypes:

                if dt == "Billing Account Master":
                    self.append("doctypes", {
                        "doctype_name": dt,
                        "perm_select": 1,
                        "perm_read": 1,
                        "perm_write": 1,
                        "perm_create": 1
                    })
                else:
                    self.append("doctypes", {
                        "doctype_name": dt,
                        "perm_select": 1,
                        "perm_read": 1
                    })


    def on_update(self):
        if not self.billing_role:
            return

        if self.doctypes and self._is_all_permissions_empty():
            self.load_existing_permissions()
        else:
            self.apply_permissions()

    # def validate(self):
    #     if not self.billing_role:
    #         return

    #     if self.doctypes and self._is_all_permissions_empty():
    #         self.load_existing_permissions()
    #     else:
    #         self.apply_permissions()


    def _is_all_permissions_empty(self):
        for row in self.doctypes:
            if any([
                row.perm_select,
                row.perm_read,
                row.perm_write,
                row.perm_create,
                row.perm_delete,
                row.perm_submit,
                row.perm_cancel,
                row.perm_amend,
                row.perm_print,
                row.perm_email,
                row.perm_report,
                row.perm_import,
                row.perm_export,
                row.perm_share,
                row.perm_if_owner
            ]): 
                return False
        return True


    def load_existing_permissions(self):

        role_name = self.billing_role

        for row in self.doctypes:

            if not row.doctype_name:
                continue

            self.reset_row_permissions(row)

            standard_perms = frappe.get_all(
                "DocPerm",
                filters={
                    "parent": row.doctype_name,
                    "role": role_name,
                    "permlevel": 0
                },
                fields=self.get_permission_fields()
            )

            custom_perms = frappe.get_all(
                "Custom DocPerm",
                filters={
                    "parent": row.doctype_name,
                    "role": role_name,
                    "permlevel": 0
                },
                fields=self.get_permission_fields()
            )

            for perm in (standard_perms + custom_perms):
                self.apply_permission_to_row(row, perm)


    def apply_permission_to_row(self, row, p):

        row.perm_select = row.perm_select or p.get("select", 0)
        row.perm_read = row.perm_read or p.get("read", 0)
        row.perm_write = row.perm_write or p.get("write", 0)
        row.perm_create = row.perm_create or p.get("create", 0)
        row.perm_delete = row.perm_delete or p.get("delete", 0)
        row.perm_submit = row.perm_submit or p.get("submit", 0)
        row.perm_cancel = row.perm_cancel or p.get("cancel", 0)
        row.perm_amend = row.perm_amend or p.get("amend", 0)
        row.perm_print = row.perm_print or p.get("print", 0)
        row.perm_email = row.perm_email or p.get("email", 0)
        row.perm_report = row.perm_report or p.get("report", 0)
        row.perm_import = row.perm_import or p.get("import", 0)
        row.perm_export = row.perm_export or p.get("export", 0)
        row.perm_share = row.perm_share or p.get("share", 0)
        row.perm_if_owner = row.perm_if_owner or p.get("if_owner", 0)


    def reset_row_permissions(self, row):
        for field in self.get_permission_fields():
            setattr(row, f"perm_{field}", 0)


    def get_permission_fields(self):
        return [
            "select",
            "read",
            "write",
            "create",
            "delete",
            "submit",
            "cancel",
            "amend",
            "print",
            "email",
            "report",
            "import",
            "export",
            "share",
            "if_owner"
        ]

    def apply_permissions(self):

        role_name = self.billing_role

        # Remove old Custom Permissions for this role
        frappe.db.delete("Custom DocPerm", {
            "role": role_name
        })

        # Create new permissions from UI
        for row in self.doctypes:

            if not row.doctype_name:
                continue

            frappe.get_doc({
                "doctype": "Custom DocPerm",
                "parent": row.doctype_name,
                "parenttype": "DocType",
                "parentfield": "permissions",
                "role": role_name,
                "permlevel": 0,
                "select": row.perm_select,
                "read": row.perm_read,
                "write": row.perm_write,
                "create": row.perm_create,
                "delete": row.perm_delete,
                "submit": row.perm_submit,
                "cancel": row.perm_cancel,
                "amend": row.perm_amend,
                "print": row.perm_print,
                "email": row.perm_email,
                "report": row.perm_report,
                "import": row.perm_import,
                "export": row.perm_export,
                "share": row.perm_share,
                "if_owner": row.perm_if_owner
            }).insert(ignore_permissions=True)

        frappe.db.commit()
