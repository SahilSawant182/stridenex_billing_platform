import frappe
from quantbit_billing_platform.utils import generate_random_id
from datetime import date
from frappe.utils import add_days


@frappe.whitelist(allow_guest=True)
def get_public_package_names():
    if frappe.local.request.method == "OPTIONS":
        frappe.local.flags.ignore_csrf = True
        frappe.response.headers = frappe._dict({
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Accept, Authorization, X-Requested-With",
            "Access-Control-Max-Age": "86400",
            "Content-Length": "0"
        })
        frappe.response.http_status_code = 204
        return ""

    frappe.local.flags.ignore_csrf = True

    packages = frappe.get_all(
        "Billing Package",
        fields=["name", "package_name", "app", "no_of_users", "package_type", "no_of_days","amount"],
        filters={"docstatus": ["!=", 2], "is_active": 1},
        order_by="package_name asc"
    )

    result = []
    for pkg in packages:
        package_data = pkg.copy()
        
        # Get app name from Billing Module Configuration
        app_name = frappe.db.get_value(
            "Billing Module Configuration",
            {"app": pkg.app},
            "name"
        )
        package_data["app_name"] = app_name or pkg.app
        
        if pkg.package_type == "Token Based":
            token_details = frappe.get_all(
                "Billing Package Token Detail",
                fields=["ref_doctype", "token_utilization_per_request"],
                filters={"parent": pkg.name, "parenttype": "Billing Package"}
            )
            package_data["billing_package_token_detail"] = token_details
        result.append(package_data)

    return result
  

@frappe.whitelist(allow_guest=True)
def get_billing_account_details(email=None, company=None):
    frappe.local.flags.ignore_csrf = True
    
    filters = {"docstatus": ["!=", 2]}
    if email:
        filters["email"] = email
    if company:
        filters["company"] = company
    
    
    users = frappe.get_all(
        "Billing Account Master",
        fields=["name", "first_name", "middle_name", "last_name", "company", "gstin", "email"],  
        filters=filters,
        order_by="first_name asc"
    )
    
    result = []
    
    for u in users:
        company_address = ""
        state = ""
        city = ""
        pincode = ""
        addr_type = "Billing"
        
        if u.company:
            addresses = frappe.get_all(
                "Address",
                filters={"address_type": "Billing", "docstatus": ["!=", 2]},
                fields=["name", "address_line1", "address_line2", "city", "state", "pincode", "country"]
            )
            
            for addr in addresses:
                link = frappe.get_all(
                    "Dynamic Link",
                    filters={
                        "parent": addr.name,
                        "link_doctype": "Company",
                        "link_name": u.company
                    },
                    limit=1
                )
                
                if link:
                    company_address = " ".join(filter(None, [addr.address_line1, addr.address_line2]))
                    state = addr.state or ""
                    city = addr.city or ""
                    pincode = addr.pincode or ""
                    break
        
        
        full_name = " ".join(filter(None, [u.first_name, u.middle_name, u.last_name]))
    
        
        u["company_address"] = company_address
        u["state"] = state
        u["city"] = city
        u["pincode"] = pincode
        u["address_type"] = addr_type
        u["gstin"] = u.gstin or ""
        u["full_name"] = full_name  
        
        result.append(u)
    
    
    result.sort(key=lambda x: x.get('full_name', ''))
    
    return result



@frappe.whitelist(allow_guest=True)
def update_billing_package(user, app_name, package_name):

    if frappe.local.request.method == "OPTIONS":
        frappe.local.flags.ignore_csrf = True
        frappe.response.headers = frappe._dict({
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Accept, Authorization, X-Requested-With",
            "Access-Control-Max-Age": "86400",
            "Content-Length": "0"
        })
        frappe.response.http_status_code = 204
        return ""

    frappe.local.flags.ignore_csrf = True

    if frappe.local.request.method == "OPTIONS":
        frappe.local.flags.ignore_csrf = True
        frappe.response.headers = frappe._dict({
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Accept, Authorization, X-Requested-With",
            "Access-Control-Max-Age": "86400",
            "Content-Length": "0"
        })
        frappe.response.http_status_code = 204
        return ""

    frappe.local.flags.ignore_csrf = True

    if not frappe.db.exists("Billing Package", package_name):
        frappe.throw(f"Billing Package '{package_name}' does not exist")

    account_name = frappe.db.get_value(
        "Billing Account Master",
        {"email": user},
        "name"
    )

    if not account_name:
        frappe.throw("Billing Account not found")

    doc = frappe.get_doc("Billing Account Master", account_name)

    updated_row = None

    pkg_role = frappe.db.get_value(
            "Billing Package",
            package_name,
            "billing_role"
        )

    for row in doc.billing_details:

        if row.app_name != app_name:
            continue

        row.billing_package = package_name
        row.billing_role = pkg_role

        ledger_exists = frappe.db.exists(
            "Billing Package Ledger",
            {
                "user": user,
                "app_name": app_name,
                "billing_package": package_name,
                "package_id": row.package_id
            }
        )

        if not ledger_exists:
            row.package_id = generate_random_id()

        updated_row = row
        break

    if not updated_row:
        frappe.throw(f"App '{app_name}' not found for user")

    for val in doc.billing_user_detail:

        if val.app_name != app_name:
            continue

        val.user_role = "User Role"

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "package_id": updated_row.package_id,
        "role": updated_row.billing_role,
        "message": f"Billing package for app '{app_name}' updated to '{package_name}'"
    }