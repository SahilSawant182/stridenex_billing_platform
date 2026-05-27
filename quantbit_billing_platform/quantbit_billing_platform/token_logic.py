import frappe

def get_master_user(user):

    is_master = frappe.db.get_value(
        "Billing Account Master",
        {"email": user, "is_master_user": 1},
        "email"
    )

    if is_master:
        return user

    masters = frappe.get_all(
        "Billing Account Master",
        filters={"is_master_user": 1},
        fields=["name", "email"]
    )

    for m in masters:

        child_users = frappe.get_all(
            "Billing User Detail",
            filters={"parent": m.name},
            pluck="email"
        )

        if user in child_users:
            return m.email

    return user

def consume_tokens(doc, method):
    
    current_user = frappe.session.user
    user = get_master_user(current_user)

    # frappe.msgprint(f"Current: {current_user} → Master: {user}")
    
    if user in ["Administrator", "Guest"]:
        return

    if getattr(frappe.local, "token_deducted", False):
        return

    frappe.local.token_deducted = True

    package = frappe.get_all(
        "Active Package Details",
        filters={"user": user},
        fields=["name", "billing_package", "remaining_tokens"]
    )

    if not package:
        return

    package = package[0]
    package_doc = frappe.get_doc("Billing Package", package.billing_package)
    if package_doc.package_type != "Token Based":
        return

    token_cost = get_token_cost(package_doc, doc.doctype)
    if token_cost == 0:
        return

    remaining = package.remaining_tokens - token_cost

    if remaining < 0:
        frappe.throw("You have exhausted your tokens.")

    frappe.db.set_value(
        "Active Package Details",
        package.name,
        "remaining_tokens",
        remaining
    )

    if remaining == 0:
        assign_user_package(user)


def get_token_cost(package_doc, doctype):
    for row in package_doc.billing_package_token_detail:
        if row.ref_doctype == doctype:
            return row.token_utilization_per_request or 0
    return 0


def assign_user_package(user):

    active = frappe.get_all(
        "Active Package Details",
        filters={"user": user},
        fields=["name", "app_name", "package_id", "billing_package"]
    )

    if not active:
        return

    active = active[0]

    # expire ledger
    ledger_name = frappe.db.get_value(
        "Billing Package Ledger",
        {
            "user": user,
            "app_name": active.app_name,
            "package_id": active.package_id,
            "status": "Active"
        },
        "name"
    )

    if ledger_name:
        frappe.db.set_value(
            "Billing Package Ledger",
            ledger_name,
            {
                "status": "Expired",
                "to_date": frappe.utils.today()
            }
        )


    pending = frappe.get_all(
        "Billing Package Ledger",
        filters={
            "user": user,
            "app_name": active.app_name,
            "status": "Pending"
        },
        order_by="creation asc",
        limit=1
    )

    if pending:
        pending = pending[0]

        pending_doc = frappe.get_doc("Billing Package Ledger", pending.name)

        # activate pending
        pending_doc.status = "Active"
        pending_doc.from_date = frappe.utils.today()

        package_doc = frappe.get_doc("Billing Package", pending_doc.billing_package)

        if package_doc.package_type == "Day Based":
            days = package_doc.no_of_days or 0
            pending_doc.to_date = frappe.utils.add_days(frappe.utils.today(), days)
        else:
            pending_doc.to_date = None

        pending_doc.save(ignore_permissions=True)

        # update active
        frappe.db.set_value(
            "Active Package Details",
            active.name,
            {
                "billing_package": pending_doc.billing_package,
                "role": pending_doc.role,
                "from_date": pending_doc.from_date,
                "to_date": pending_doc.to_date,
                "package_id": pending_doc.package_id
            }
        )

        ensure_ledger_exists(
            user,
            active.app_name,
            pending_doc.billing_package,
            pending_doc.role,
            pending_doc.package_id
        )

        update_user_role(user, pending_doc.role)

        update_billing_master(
            user,
            active.app_name,
            pending_doc.billing_package,
            pending_doc.role
        )

        return   
    

    user_package = "User Package"

    package_doc = frappe.get_doc("Billing Package", user_package)

    new_package_id = frappe.generate_hash(length=10)

    frappe.db.set_value(
        "Active Package Details",
        active.name,
        {
            "billing_package": user_package,
            "role": package_doc.billing_role,
            "from_date": frappe.utils.today(),
            "to_date": None,
            "package_id": new_package_id
        }
    )

    new_ledger = frappe.new_doc("Billing Package Ledger")
    new_ledger.user = user
    new_ledger.app_name = active.app_name
    new_ledger.billing_package = user_package
    new_ledger.role = package_doc.billing_role
    new_ledger.package_id = new_package_id
    new_ledger.status = "Active"
    new_ledger.from_date = frappe.utils.today()
    new_ledger.insert(ignore_permissions=True)

    ensure_ledger_exists(
        user,
        active.app_name,
        user_package,
        package_doc.billing_role,
        new_package_id
    )

    update_user_role(user, package_doc.billing_role)

    update_billing_master(
        user,
        active.app_name,
        user_package,
        package_doc.billing_role
    )



def ensure_ledger_exists(user, app_name, package, role, package_id):

    exists = frappe.db.exists(
        "Billing Package Ledger",
        {
            "user": user,
            "app_name": app_name,
            "package_id": package_id
        }
    )

    if not exists:
        new_ledger = frappe.new_doc("Billing Package Ledger")
        new_ledger.user = user
        new_ledger.app_name = app_name
        new_ledger.billing_package = package
        new_ledger.role = role
        new_ledger.package_id = package_id
        new_ledger.status = "Active"
        new_ledger.from_date = frappe.utils.today()
        new_ledger.insert(ignore_permissions=True)


def update_user_role(user, role):

    user_doc = frappe.get_doc("User", user)

    user_doc.roles = []

    user_doc.append("roles", {"role": "All"})
    user_doc.append("roles", {"role": "Desk User"})

    if role:
        user_doc.append("roles", {"role": role})

    user_doc.save(ignore_permissions=True)


def update_billing_master(user, app_name, package, role):

    master_name = frappe.db.get_value(
        "Billing Account Master",
        {"email": user}
    )

    if not master_name:
        return

    master_doc = frappe.get_doc("Billing Account Master", master_name)

    updated = False

    for row in master_doc.billing_details:
        if row.app_name == app_name:
            row.billing_package = package
            row.billing_role = role
            updated = True

    if updated:
        master_doc.flags.ignore_sync = True
        master_doc.save(ignore_permissions=True)