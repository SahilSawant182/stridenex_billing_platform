import frappe

ROLE_PERMISSIONS = {
    "Billing Role Creator": {
        "doctypes": [
            "Billing Role",
            "Billing Role Permission Setting"
        ],
        "perms": {
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1
        }
    },

    "Package Manager": {
        "doctypes": [
            "Billing Package",
            "Billing Package Ledger",
            "Active Package Details"
        ],
        "perms": {
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1
        }
    },

    "Billing Module Configurator": {
        "doctypes": [
            "Billing Module Configuration",
            "Application Features"
        ],
        "perms": {
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1
        }
    },

    "Billing Account Creator": {
        "doctypes": [
            "Billing Account Master"
        ],
        "perms": {
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1
        }
    },

    "Billing Notifier": {
        "doctypes": [
            "Billing Notification"
        ],
        "perms": {
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1
        }
    },

    "Payment Platform Integrator": {
        "doctypes": [
            "Billing Settings"
        ],
        "perms": {
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1
        }
    },

    "Billing Coupon Creator": {
        "doctypes": [
            "Billing Coupon Code",
            "Billing Pricing Rule"
        ],
        "perms": {
            "read": 1,
            "write": 1,
            "create": 1,
            "delete": 1
        }
    },

    "User Role": {
        "doctypes": [
            "Active Package Details",
            "Application Feature",
            "Billing Account Master",
            "Billing Module Configuration",
            "Billing Notification",
            "Billing Package",
            "Billing Package Ledger",
            "Billing Role",
            "Billing Role Permission Setting",
            "Billing Settings",
            "Billing Coupon Code",
            "Billing Pricing Rule"
        ],
        "perms": {
            "read": 1,
            "select": 1
        }
    }
}


def after_install():
    setup_billing_roles_and_permissions()


def setup_billing_roles_and_permissions():
    for role_name, config in ROLE_PERMISSIONS.items():

        # Create Role if not exists
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({
                "doctype": "Role",
                "role_name": role_name,
                "desk_access": 1
            }).insert(ignore_permissions=True)

            frappe.db.commit()

        # Create Custom DocPerms
        for dt in config.get("doctypes", []):

            if not frappe.db.exists(
                "Custom DocPerm",
                {
                    "parent": dt,
                    "role": role_name
                }
            ):

                perm = frappe.new_doc("Custom DocPerm")

                perm.parent = dt
                perm.parenttype = "DocType"
                perm.parentfield = "permissions"
                perm.role = role_name

                # Assign permissions
                for p_key, p_val in config.get("perms", {}).items():
                    perm.set(p_key, p_val)

                perm.insert(ignore_permissions=True)

                frappe.db.commit()