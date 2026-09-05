import frappe
from frappe import _
import json
import os
from quantbit_billing_platform.utils import generate_random_id
from datetime import timedelta
from frappe.utils import today, getdate, add_days, now_datetime, get_datetime
# from quantbit_billing_platform.quantbit_billing_platform.doctype.billing_account_master.billing_account_master import set_default_company_boot

@frappe.whitelist()
def send_notification_to_user():

	records = frappe.db.sql("""
		SELECT 
			apd.name,
			apd.user,
			apd.app_name,
			apd.to_date,
			bp.notify_before_days
		FROM `tabActive Package Details` apd
		JOIN `tabBilling Package` bp
			ON apd.billing_package = bp.name
	""", as_dict=True)

	current_datetime = now_datetime()

	for record in records:

		if not record.to_date or not record.notify_before_days:
			continue

		expiry_datetime = get_datetime(record.to_date).replace(
			hour=23,
			minute=59,
			second=59
		)

		notify_datetime = expiry_datetime - timedelta(days=record.notify_before_days)

		today_date = current_datetime.date()
		notify_date = notify_datetime.date()
		expiry_date = expiry_datetime.date()

		if notify_date <= today_date <= expiry_date:

			remaining_days = (expiry_datetime.date() - current_datetime.date()).days

			priority = "Low"

			if remaining_days <= 2:
				priority = "High"
			elif remaining_days <= 5:
				priority = "Medium"

			existing_notification = frappe.db.exists(
				"Billing Notification",
				{
					"user": record.user,
					"subject": f"Billing Package Expiring Soon - {record.app_name}"
				}
			)

			if existing_notification:
				continue

			frappe.get_doc({
				"doctype": "Billing Notification",
				"subject": f"Billing Package Expiring Soon - {record.app_name}",
				"user": record.user,
				"billing_role": None,
				"from_date": current_datetime,
				"to_date": expiry_datetime,
				"priority": priority,
				"message": f"""
					Your billing package for <b>{record.app_name}</b>
					will expire on <b>{expiry_datetime}</b>.
				"""
			}).insert(ignore_permissions=True)
			frappe.db.commit()

	 


# def custom_boot_session(bootinfo):
# 	set_default_company_boot(bootinfo)

# 	roles = []

# 	account = frappe.db.get_value(
# 		"Billing Account Master",
# 		{"email": frappe.session.user},
# 		"name"
# 	)

# 	if account:

# 		roles = frappe.get_all(
# 			"Billing Acount Billing Details",
# 			filters={"parent": account},
# 			pluck="billing_role"
# 		)

# 	bootinfo.billing_roles = roles or []


@frappe.whitelist()
def expire_billing_packages():

	today_date = getdate(today())

	expired_packages = frappe.get_all(
		"Active Package Details",
		fields=[
			"name",
			"user",
			"app_name",
			"package_id",
			"to_date",
			"package_type",
			"remaining_tokens"
		]
	)

	for pkg in expired_packages:

		# if(pkg.package_type == "Token Based" and pkg.remaining_tokens == 0):

		if pkg.to_date == None:
			continue

		is_day_expired = pkg.to_date and pkg.to_date < today_date
		is_token_expired = (
			pkg.package_type == "Token Based"
			and pkg.remaining_tokens == 0
		)

		if not (is_day_expired or is_token_expired):
			continue

		# Expire current ledger
		frappe.db.set_value(
			"Billing Package Ledger",
			{"package_id": pkg.package_id},
			"status",
			"Expired"
		)

		# Get pending
		pending = frappe.get_all(
			"Billing Package Ledger",
			filters={
				"user": pkg.user,
				"app_name": pkg.app_name,
				"status": "Pending"
			},
			fields=["name", "role", "billing_package", "package_id", "days_left", "from_date"],
			order_by="creation desc",
			limit=1
		)

		if not pending:

			default = frappe.db.get_value(
				"Billing Package",
				{"is_user_package": 1},
				["name", "billing_role"],
				as_dict=True
			)

			if not default:
				frappe.throw("No User Package configured...")

			new_package = default.name
			new_role = default.billing_role
			new_package_id = generate_random_id()
			new_from = today_date
			new_to = None

		else:
			pending = pending[0]

			frappe.db.set_value("Billing Package Ledger", pending.name, "status", "Active")

			new_package = pending.billing_package
			new_role = pending.role
			new_package_id = pending.package_id
			new_from = pending.from_date
			new_to = add_days(today_date, pending.days_left or 0)


		# if not default:
		#     frappe.throw("No User Package configured. Please mark one package as 'Is User Package'.")
		# Update active
		frappe.db.set_value(
			"Active Package Details",
			pkg.name,
			{
				"role": new_role,
				"billing_package": new_package,
				"package_id": new_package_id,
				"from_date": new_from,
				"to_date": new_to
			}
		)

		exists = frappe.db.exists(
			"Billing Package Ledger",
			{
				"user": pkg.user,
				"app_name": pkg.app_name,
				"package_id": new_package_id
			}
		)

		if not exists:
			new_ledger = frappe.new_doc("Billing Package Ledger")
			new_ledger.user = pkg.user
			new_ledger.app_name = pkg.app_name
			new_ledger.billing_package = new_package
			new_ledger.role = new_role
			new_ledger.package_id = new_package_id
			new_ledger.status = "Active"
			new_ledger.from_date = new_from
			new_ledger.to_date = new_to
			new_ledger.insert(ignore_permissions=True)
			
		# Sync Billing Account
		account = frappe.db.get_value(
			"Billing Account Master",
			{"email": pkg.user},
			"name"
		)

		if not account:
			continue

		# update billing details
		rows = frappe.get_all(
			"Billing Acount Billing Details",
			filters={"parent": account, "app_name": pkg.app_name},
			pluck="name"
		)

		for r in rows:
			frappe.db.set_value(
				"Billing Acount Billing Details",
				r,
				{
					"billing_package": new_package,
					"billing_role": new_role,
					"package_id": new_package_id
				}
			)

		master_doc = frappe.get_doc("Billing Account Master", account)
		master_doc.sync_users()

		# update user role
		user_rows = frappe.get_all(
			"Billing User Detail",
			filters={"parent": account, "app_name": pkg.app_name},
			pluck="name"
		)

		for ur in user_rows:

			frappe.db.set_value(
				"Billing User Detail",
				ur,
				"user_role",
				"User Role"
			)

			email = frappe.db.get_value("Billing User Detail", ur, "email")

			if not email:
				continue

			base_doc_name = frappe.db.get_value(
				"Billing Account Master",
				{"email": email},
				"name"
			)

			if not base_doc_name:
				continue

			base_doc = frappe.get_doc("Billing Account Master", base_doc_name)

			updated = False

			for d in base_doc.billing_details:
				if d.app_name == pkg.app_name:
					if d.billing_role != "User Role":
						d.billing_role = "User Role"
						updated = True

			if updated:
				base_doc.flags.ignore_sync = True
				base_doc.flags.ignore_active_package_sync = True
				base_doc.save(ignore_permissions=True)
				base_doc.sync_users()
				



@frappe.whitelist(allow_guest=True)
def get_billing_url():
	try:
		billing_settings = frappe.get_single("Billing Settings")
	except Exception:
		return "/registration"

	sys_url = getattr(billing_settings, "sys_url", None)
	if not sys_url:
		return "/registration"

	sys_url = sys_url.rstrip("/")

	# This will now correctly return http://110.225.251.16:4452 after setting host_name
	from_site = frappe.utils.get_url(full_address=True)

	# Optional: Let Billing Settings override if you add the field later
	if hasattr(billing_settings, "current_site_url") and billing_settings.current_site_url:
		from_site = billing_settings.current_site_url

	from_site = from_site.rstrip("/")

	return f"{sys_url}/plans?from_site={from_site}"


@frappe.whitelist(allow_guest=True)
def get_billing_url_partner_portal():
	try:
		billing_settings = frappe.get_single("Billing Settings")
	except Exception:
		return "/registration"

	sys_url = getattr(billing_settings, "sys_url", None)
	if not sys_url:
		return "/registration"

	sys_url = sys_url.rstrip("/")

	# This will now correctly return http://110.225.251.16:4452 after setting host_name
	from_site = frappe.utils.get_url(full_address=True)

	# Optional: Let Billing Settings override if you add the field later
	if hasattr(billing_settings, "current_site_url") and billing_settings.current_site_url:
		from_site = billing_settings.current_site_url

	from_site = from_site.rstrip("/")

	return f"{sys_url}/partner-portal?from_site={from_site}"



@frappe.whitelist()
def expire_token_on_date():

	today_date = today()

	accounts = frappe.get_all(
		"Active Package Details",
		filters={"to_date": ["<", today_date], "package_type": "Token Based", "remaining_tokens": [">", 0]},
		fields=["name"]
	)

	for account in accounts:
		frappe.db.set_value(
			"Active Package Details",
			account.name,
			{
				"remaining_tokens": 0
			}
		)



import frappe
from frappe.utils.pdf import get_pdf
import re

@frappe.whitelist(allow_guest=True)
def download_payment_invoice(name):

	if not name:
		frappe.throw("Name is required")

	try:
		frappe.local.login_manager = None
		frappe.set_user("Administrator")

		if not frappe.db.exists("Payment Invoice Details", name):
			frappe.throw("Payment Invoice Details not found")

		doc = frappe.get_doc("Payment Invoice Details", name)

		# Get customer name
		customer_name = doc.get("customer_name") or doc.get("customer") or "Customer"

		# Clean filename
		customer_name = re.sub(r'[^A-Za-z0-9 ]+', '', customer_name).strip()
		customer_name = customer_name.replace(" ", "_")

		# File name format: INVOICEID_CustomerName.pdf
		file_name = f"{name}_{customer_name}.pdf"

		# Generate HTML first
		html = frappe.get_print(
			doctype="Payment Invoice Details",
			name=name,
			print_format="Payment Invoice Details",
			no_letterhead=1
		)

		# Force compact single-page PDF
		options = {
			"page-size": "A4",
			"margin-top": "5mm",
			"margin-bottom": "5mm",
			"margin-left": "5mm",
			"margin-right": "5mm",
			"encoding": "UTF-8",
			"print-media-type": None,
			"enable-local-file-access": None,
			"disable-smart-shrinking": "",
			"zoom": "0.80"
		}

		pdf = get_pdf(html, options=options)

		frappe.local.response.filename = file_name
		frappe.local.response.filecontent = pdf
		frappe.local.response.type = "download"

	except Exception:
		frappe.log_error(
			title="Download Payment Invoice Error",
			message=frappe.get_traceback()
		)
		frappe.throw("Unable to generate invoice PDF")












# method/quantbit_billing_platform/quantbit_billing_platform/api.get_user_packages

# stridnex api
@frappe.whitelist(allow_guest=True)
def get_user_packages(email):
    """
    Returns the assigned packages for a given user email from the Billing Account Master.
    """
    if not frappe.db.exists("Billing Account Master", email):
        return {"error": "Billing Account Master not found for this email."}

    doc = frappe.get_doc("Billing Account Master", email)

    # Extract relevant fields from the billing_details child table
    packages = [
        {
            "app_name": row.app_name,
            "billing_package": row.billing_package,
            "package_id": row.package_id,
            "billing_role": row.billing_role
        }
        for row in doc.get("billing_details", [])
    ]

    return {
        "email": email,
        "active_packages": packages
    }


#stridnex api

@frappe.whitelist(allow_guest=True)
def get_billing_packages_by_type(account_type):
    if not account_type:
        return {"error": "The 'account_type' parameter is required."}

    raw_packages = frappe.get_all(
        "Billing Package",
        filters={
            "is_active": 1,
            "target_account_type": ["in", [account_type, "All"]],
			"is_base_package": 0,
        "is_user_package": 0
        },
        fields=["name", "package_name", "amount", "package_type", "no_of_days", "app_name", "is_tax_inclusive"],
        order_by="amount asc"
    )

    clean_packages = []

    for pkg in raw_packages:
        child_features = frappe.get_all(
            "Package Feature",
            filters={
                "parent": pkg.name, 
                "parenttype": "Billing Package"
            },
            fields=["feature"],
            order_by="idx asc"
        )

        feature_list = []
        for row in child_features:
            if row.feature:
                lines = [line.strip() for line in row.feature.split('\n') if line.strip()]
                feature_list.extend(lines)

        clean_packages.append({
            "package_name": pkg.package_name,
            "amount": pkg.amount,
            "package_type": pkg.package_type,
            "no_of_days": pkg.no_of_days,
            "features": feature_list,
			"app_name": pkg.app_name,
            "is_tax_inclusive": int(pkg.is_tax_inclusive or 0)
        }) 

    return {
        "status": "success", 
        "data": clean_packages
    }










# Stridenext post to update billing package
@frappe.whitelist(allow_guest=True)
def update_billing_account_package(email, package_name, app_name=None, sales_invoice_name=None):
    """
    Dedicated endpoint called cross-site after payment.
    Runs on the devstridenex site where Billing Account Master exists.
    """
    if not email or not package_name:
        frappe.throw("Email and package_name are required")

    if not frappe.db.exists("Billing Account Master", email):
        frappe.throw(f"No Billing Account Master found for: {email}")

    doc = frappe.get_doc("Billing Account Master", email)
    

    billing_details = doc.get("billing_details") or []
    
    if billing_details:
        for detail in billing_details:
            detail.billing_package = package_name	
            if app_name:
                detail.app_name = app_name
    else:
        doc.append("billing_details", {
            "billing_package": package_name,
            "app_name": app_name or ""
        })

    doc.last_payment_date = today()
    if sales_invoice_name:
        doc.last_payment_invoice = sales_invoice_name
        
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    
    return {"status": "success", "name": doc.name}






# method/quantbit_billing_platform.quantbit_billing_platform.api.get_remaining_days
# 
#api for remaining days	
@frappe.whitelist(allow_guest=True)
def get_remaining_days(user):
    if not user:
        return {
            "success": False,
            "message": "User is required"
        }

    package = frappe.get_value(
        "Active Package Details",
        {"user": user},
        ["billing_package", "from_date", "to_date"],
        as_dict=True
    )

    if not package:
        return {
            "success": False,
            "message": "No active package found"
        }

    today = getdate()
    to_date = getdate(package.to_date)

    remaining_days = (to_date - today).days

    if remaining_days <= 0:
        return {
            "success": False,
            "status": "Expired",
            "message": "Package expired",
            "remaining_days": 0
        }

    return {
        "success": True,
        "status": "Active",
        "billing_package": package.billing_package,
        "from_date": package.from_date,
        "to_date": package.to_date,
        "remaining_days": remaining_days
    }









# # method/quantbit_billing_platform.quantbit_billing_platform.api.allocate_package_quotas
# # api to update the user feauture quota when the user package is updated	
# import frappe

# def allocate_package_quotas(doc, method=None):
#     """Rebuilds the child table natively and strictly mirrors active packages."""
#     assigned_features = {}

#     # 1. Gather all features and limits from currently assigned packages
#     if doc.get("billing_details"):
#         for row in doc.billing_details:
#             if not row.billing_package:
#                 continue
 
#             package_limits = frappe.get_all(
#                 "App Feature Details",
#                 filters={"parent": row.billing_package, "parenttype": "Billing Package"},
#                 fields=["feature_list", "usage_limit"]
#             )

#             for limit in package_limits:
#                 if limit.feature_list:
#                     current_stored_limit = assigned_features.get(limit.feature_list, -1)
#                     new_limit = limit.usage_limit or 0
					
                    
#                     # Logic for merging multiple packages: 
#                     # 0 means Unlimited. If any package grants 0, keep it 0.
#                     # Otherwise, store the highest numerical limit.
#                     if current_stored_limit == 0 or new_limit == 0:
#                         assigned_features[limit.feature_list] = 0
#                     elif new_limit > current_stored_limit:
#                         assigned_features[limit.feature_list] = new_limit

#     # 2. Extract existing usage BEFORE clearing the table so data isn't lost
#     existing_usage = {}
#     if doc.get("feature_quotas"):
#         for row in doc.feature_quotas:
#             existing_usage[row.feature] = row.used_count

#     # 3. WIPE the old table completely. 
#     # (If assigned_features is empty, it stays empty. Old limits are destroyed).
#     doc.set("feature_quotas", [])

#     # 4. Rebuild strictly with authorized features
#     for feature_name, total_limit in assigned_features.items():
#         doc.append("feature_quotas", {
#             "feature": feature_name,
#             "total_limit": total_limit,
#             "used_count": existing_usage.get(feature_name, 0)
#         })


# @frappe.whitelist()
# def consume_quota(feature_code):
#     user_email = frappe.session.user
    
#     feature_name = frappe.db.get_value("Application Features", {"feature_code": feature_code}, "name")
#     if not feature_name:
#         frappe.throw(f"Invalid feature code: {feature_code}")

#     # Atomic SQL: added `total_limit = 0` to allow infinite usage
#     frappe.db.sql("""
#         UPDATE `tabUser Quota Tracker`
#         SET used_count = used_count + 1
#         WHERE parent = %s 
#           AND parenttype = 'Billing Account Master'
#           AND feature = %s 
#           AND (total_limit = 0 OR used_count < total_limit)
#     """, (user_email, feature_name))
    
#     if frappe.db.sql("SELECT ROW_COUNT()")[0][0] == 0:
#         frappe.throw("Quota exhausted or feature not allocated to your current package.")
        
#     frappe.db.commit()
#     return {"status": "success", "message": "Quota consumed."}


# @frappe.whitelist()
# def get_user_entitlements():
#     user_email = frappe.session.user
    
#     quotas = frappe.db.get_all(
#         "User Quota Tracker",
#         filters={"parent": user_email, "parenttype": "Billing Account Master"},
#         fields=["feature", "total_limit", "used_count"]
#     )
    
#     entitlements = {}
#     for q in quotas:
#         feature_code = frappe.db.get_value("Application Features", q.feature, "feature_code")
#         if feature_code:
#             # Format UI response so React knows if it's unlimited
#             if q.total_limit == 0:
#                 remaining = "Unlimited"
#                 limit_display = "Unlimited"
#             else:
#                 remaining = q.total_limit - q.used_count
#                 limit_display = q.total_limit
                
#             entitlements[feature_code] = {
#                 "limit": limit_display,
#                 "used": q.used_count,
#                 "remaining": remaining
#             }
            
#     return entitlements








from frappe.utils import getdate, today, date_diff
# builds
def allocate_package_quotas(doc, method=None):
    """Rebuilds the child table and registers reset frequencies."""
    assigned_features = {}

    # 1. Gather all features, limits, and frequencies from currently assigned packages
    if doc.get("billing_details"):
        for row in doc.billing_details:
            if not row.billing_package:
                continue

            package_limits = frappe.get_all(
                "App Feature Details",
                filters={"parent": row.billing_package, "parenttype": "Billing Package"},
                fields=["feature_list", "usage_limit", "reset_frequency"]
            )

            for limit in package_limits:
                if limit.feature_list:
                    current_data = assigned_features.get(limit.feature_list, {"limit": -1, "freq": "None"})
                    new_limit = limit.usage_limit or 0
                    
                    target_limit = current_data["limit"]
                    if target_limit == 0 or new_limit == 0:
                        target_limit = 0
                    elif new_limit > target_limit:
                        target_limit = new_limit

                    assigned_features[limit.feature_list] = {
                        "limit": target_limit,
                        "freq": limit.reset_frequency or "None"
                    }

    is_renewal = doc.get("reset_quotas")
    existing_usage = {}
    existing_dates = {}
    
    # 2. Extract existing usage BEFORE clearing the table
    if not is_renewal and doc.get("feature_quotas"):
        for row in doc.feature_quotas:
            existing_usage[row.feature] = row.used_count
            existing_dates[row.feature] = row.last_reset_date

    doc.set("feature_quotas", [])

    # 3. Rebuild strictly with authorized features and their reset dates
    for feature_name, data in assigned_features.items():
        doc.append("feature_quotas", {
            "feature": feature_name,
            "total_limit": data["limit"],
            "reset_frequency": data["freq"],
            "used_count": 0 if is_renewal else existing_usage.get(feature_name, 0),
            "last_reset_date": today() if is_renewal or not existing_dates.get(feature_name) else existing_dates.get(feature_name)
        })
        
    if is_renewal:
        doc.reset_quotas = 0


def evaluate_and_reset_cycles(user_email):
    """Checks if a periodic quota needs a reset before an action occurs."""
    quotas = frappe.db.get_all(
        "User Quota Tracker",
        filters={"parent": user_email, "parenttype": "Billing Account Master", "reset_frequency": ["!=", "None"]},
        fields=["name", "reset_frequency", "last_reset_date"]
    )
    
    current_date = getdate(today())

    for q in quotas:
        if not q.last_reset_date:
            continue
            
        days_passed = date_diff(current_date, getdate(q.last_reset_date))
        needs_reset = False

        if q.reset_frequency == "Daily" and days_passed >= 1:
            needs_reset = True
        elif q.reset_frequency == "Weekly" and days_passed >= 7:
            needs_reset = True
        elif q.reset_frequency == "Monthly" and days_passed >= 30:
            needs_reset = True

        if needs_reset:
            # Wipe usage and start the new cycle clock today
            frappe.db.set_value("User Quota Tracker", q.name, {
                "used_count": 0,
                "last_reset_date": current_date
            })
    
    frappe.db.commit()


@frappe.whitelist()
def consume_quota(feature_code):
    user_email = frappe.session.user
    
    # Trigger the background reset check FIRST
    evaluate_and_reset_cycles(user_email)
    
    feature_name = frappe.db.get_value("Application Features", {"feature_code": feature_code}, "name")
    if not feature_name:
        frappe.throw(f"Invalid feature code: {feature_code}")
     
    frappe.db.sql("""
        UPDATE `tabUser Quota Tracker`
        SET used_count = used_count + 1
        WHERE parent = %s 
          AND parenttype = 'Billing Account Master'
          AND feature = %s 
          AND (total_limit = 0 OR used_count < total_limit)
    """, (user_email, feature_name))
    
    if frappe.db.sql("SELECT ROW_COUNT()")[0][0] == 0:
        frappe.throw("Quota exhausted or feature not allocated to your current package.")
        
    frappe.db.commit()
    return {"status": "success", "message": "Quota consumed."}


@frappe.whitelist()
def get_user_entitlements():
    user_email = frappe.session.user
    
    # Trigger the background reset check FIRST so React gets accurate data
    evaluate_and_reset_cycles(user_email)
	
    quotas = frappe.db.get_all(
        "User Quota Tracker",
        filters={"parent": user_email, "parenttype": "Billing Account Master"},
        fields=["feature", "total_limit", "used_count", "reset_frequency"]
    )
    
    entitlements = {}
    for q in quotas:
        feature_code = frappe.db.get_value("Application Features", q.feature, "feature_code")
        if feature_code:
            if q.total_limit == 0:
                remaining = "Unlimited"
                limit_display = "Unlimited"
            else:
                remaining = q.total_limit - q.used_count
                limit_display = q.total_limit
                
            entitlements[feature_code] = {
                "limit": limit_display,
                "used": q.used_count,
                "remaining": remaining,
                "frequency": q.reset_frequency or "None"
            }
    return entitlements	

	


@frappe.whitelist(allow_guest=True)
def create_subscription_history(**kwargs):

    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.throw("Authentication required", frappe.AuthenticationError)

    data = kwargs or frappe.request.json or {}

    sales_invoice_no = data.get("sales_invoice_no") or ""
    customer_email   = data.get("customer_email") or ""
    if not sales_invoice_no:
        frappe.throw("sales_invoice_no is required")

    if not customer_email:
        frappe.throw("customer_email is required")

    # ---- Idempotent duplicate check ----
    existing = frappe.db.get_value(
        "Subscription History",
        {"sales_invoice_no": sales_invoice_no},
        "name"
    )

    if existing:
        frappe.log_error(
            title="Subscription History - Duplicate Skipped",
            message={
                "sales_invoice_no": sales_invoice_no,
                "existing_record": existing
            }
        )
        return {
            "status": "success",
            "message": "Subscription History already exists",
            "name": existing,
            "created": False
        }

    # ---- expiry_date calculation ----
    from frappe.utils import getdate, add_days, today as frappe_today

    raw_purchase_date = data.get("purchase_date")
    try:
        purchase_date = getdate(raw_purchase_date) if raw_purchase_date else getdate(frappe_today())
    except Exception:
        purchase_date = getdate(frappe_today())

    duration = 0
    try:
        duration = int(data.get("duration") or 0)
    except (ValueError, TypeError):
        duration = 0

    expiry_date = add_days(purchase_date, duration) if duration > 0 else None

    # ---- Enforce single active subscription per customer ----
    # Deactivate ALL currently active records for this customer in one bulk
    # operation so there is never more than one active subscription at a time.
    previously_active = frappe.get_all(
        "Subscription History",
        filters={
            "customer_email": customer_email,
            "is_active": 1,
            "package_type": ["in", ["Day Based", "Token Based"]],
        },
        pluck="name",
    )

    if previously_active:
        frappe.db.set_value(
            "Subscription History",
            {
                "customer_email": customer_email,
                "is_active": 1,
                "package_type": ["in", ["Day Based", "Token Based"]],
            },
            "is_active",
            0,
            update_modified=False,
        )
        frappe.log_error(
            title="Subscription History - Previous Subscriptions Deactivated",
            message={
                "customer_email": customer_email,
                "deactivated_records": previously_active,
                "deactivated_count": len(previously_active),
            },
        )

    # ---- Insert new Subscription History (always active) ----
    doc = frappe.new_doc("Subscription History")

    doc.customer_email      = customer_email
    doc.customer_name       = data.get("customer_name") or ""
    doc.package_name        = data.get("package_name") or ""
    doc.package_type        = data.get("package_type") or ""
    doc.app_name            = data.get("app_name") or ""
    doc.duration            = duration
    doc.amount              = data.get("amount") or 0
    doc.currency            = data.get("currency") or "INR"
    doc.discount            = data.get("discount") or 0
    doc.payment_status      = data.get("payment_status") or "Paid"
    doc.purchase_date       = purchase_date
    doc.expiry_date         = expiry_date
    doc.is_active           = 1
    doc.sales_invoice_no    = sales_invoice_no
    doc.payment_entry_no    = data.get("payment_entry_no") or ""
    doc.razorpay_payment_id = data.get("razorpay_payment_id") or ""
    doc.site                = data.get("site") or ""

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    frappe.log_error(
        title="Subscription History Inserted",
        message={
            "name": doc.name,
            "sales_invoice_no": sales_invoice_no,
            "customer_email": customer_email,
            "purchase_date": str(purchase_date),
            "expiry_date": str(expiry_date) if expiry_date else None,
            "duration": duration
        }
    )

    return {
        "status": "success",
        "message": "Subscription History created successfully",
        "name": doc.name,
        "created": True,
        "expiry_date": str(expiry_date) if expiry_date else None
    }


# ---------------------------------------------------------------------------
# Subscription Dashboard API
# ---------------------------------------------------------------------------
# Single endpoint for the Next.js frontend — returns everything it needs
# about the logged-in user's subscriptions in one call.
#
# Response shape:
# {
#     "status": "success",
#     "summary": { ... },
#     "active_subscription": { ... } | null,
#     "history": [ ... ]
# }
# ---------------------------------------------------------------------------

# Fields we expose publicly — never leak internal Frappe meta columns.
_HISTORY_FIELDS = [
    "name",
    "package_name",
    "package_type",
    "app_name",
    "amount",
    "discount",
    "currency",
    "payment_status",
    "purchase_date",
    "expiry_date",
    "is_active",
    "sales_invoice_no",
]


def _get_current_running_package(email):
    """
    Fetch the user's currently running package.

    Priority:
    1. Subscription History with is_active=1 and payment_status=Paid
       (the real paid plan the user is on right now — newest wins)
    2. Active Package Details (base/free/onboarding package fallback)

    Returns a clean dict or None if nothing found.
    """
    from frappe.utils import today, getdate

    # ── Priority 1: active paid plan from Subscription History ──────────────
    paid_active = frappe.get_all(
        "Subscription History",
        filters={
            "customer_email": email,
            "payment_status": "Paid",
            "is_active": 1,
            "package_type": ["in", ["Day Based", "Token Based"]],
        },
        fields=[
            "name", "package_name", "package_type", "app_name",
            "purchase_date", "expiry_date",
            "amount", "currency", "sales_invoice_no",
        ],
        order_by="purchase_date desc, name desc",
        limit=1,
    )

    if paid_active:
        rec = paid_active[0]
        return {
            "billing_package":  rec.get("package_name"),
            "package_name":     rec.get("package_name"),
            "package_type":     rec.get("package_type"),
            "app_name":         rec.get("app_name"),
            "from_date":        str(rec["purchase_date"]) if rec.get("purchase_date") else None,
            "to_date":          str(rec["expiry_date"])   if rec.get("expiry_date")   else None,
            "package_id":       rec.get("name"),
            "remaining_tokens": None,
            "total_tokens":     None,
            "amount":           float(rec.get("amount") or 0),
            "currency":         rec.get("currency") or "INR",
            "sales_invoice_no": rec.get("sales_invoice_no"),
            "source":           "subscription_history",
        }

    # ── Priority 2: base/free package from Active Package Details ────────────
    pkg = frappe.db.get_value(
        "Active Package Details",
        {"user": email, "status": "Active"},
        [
            "name",
            "billing_package",
            "app_name",
            "package_type",
            "from_date",
            "to_date",
            "package_id",
            "remaining_tokens",
            "total_tokens",
        ],
        as_dict=True,
    )

    if not pkg:
        # Try without status filter as last resort
        pkg = frappe.db.get_value(
            "Active Package Details",
            {"user": email},
            [
                "name",
                "billing_package",
                "app_name",
                "package_type",
                "from_date",
                "to_date",
                "package_id",
                "remaining_tokens",
                "total_tokens",
            ],
            as_dict=True,
        )

    if not pkg:
        return None

    # Resolve the human-readable package name from the Billing Package doctype.
    package_name = frappe.db.get_value(
        "Billing Package", pkg.billing_package, "package_name"
    ) or pkg.billing_package

    return {
        "billing_package":  pkg.billing_package,
        "package_name":     package_name,
        "package_type":     pkg.package_type,
        "app_name":         pkg.app_name,
        "from_date":        str(pkg.from_date) if pkg.from_date else None,
        "to_date":          str(pkg.to_date)   if pkg.to_date   else None,
        "package_id":       pkg.package_id,
        "remaining_tokens": pkg.remaining_tokens,
        "total_tokens":     pkg.total_tokens,
        "source":           "active_package",   # base/free plan from Active Package Details
    }



def _build_empty_dashboard(current_plan=None):
    """Return the canonical empty-state response when a user has no paid history."""
    summary = {
        "total_spent": 0,
        "total_purchases": 0,
        "active_subscription": False,
    }

    # Even with no purchase history the user may be on a base/free plan.
    if current_plan:
        summary["current_package"]      = current_plan.get("package_name")
        summary["current_package_type"] = current_plan.get("package_type")
        summary["next_expiry"]          = current_plan.get("to_date")

    return {
        "status":              "success",
        "summary":             summary,
        "active_subscription": None,
        "current_plan":        current_plan,   # base/user/free package from Active Package Details
        "history":             [],
    }


def _pick_active(records):
    """
    Given a list of Subscription History records, return the single active one.

    Rules:
    - Prefer records where is_active == 1.
    - If multiple active records exist (legacy data), return the newest by
      purchase_date (ties broken by name desc which is creation-order).
    - Returns None when no active record exists.
    """
    active_records = [r for r in records if r.get("is_active")]
    if not active_records:
        return None

    # Sort newest-first: primary by purchase_date, secondary by name (creation order)
    active_records.sort(
        key=lambda r: (
            str(r.get("purchase_date") or ""),
            r.get("name") or "",
        ),
        reverse=True,
    )
    return active_records[0]


def _build_summary(records, current_plan=None):
    """
    Compute the summary block from the full history list and the active record.

    total_spent     = sum of `amount` where payment_status == "Paid"
    total_purchases = total number of records (regardless of status)

    current_package / next_expiry / active_subscription:
      Always shown from the Active Package Details (current_plan).
    """
    total_spent = sum(
        float(r.get("amount") or 0)
        for r in records
        if r.get("payment_status") == "Paid"
    )

    summary = {
        "total_spent": total_spent,
        "total_purchases": len(records),
        "active_subscription": bool(current_plan),
    }

    if current_plan:
        summary["current_package"]      = current_plan.get("package_name")
        summary["current_package_type"] = current_plan.get("package_type")
        summary["next_expiry"]          = current_plan.get("to_date")

    return summary


def _format_history_item(record):
    """
    Return a clean dict with only the fields the frontend needs.
    Converts date objects to ISO strings so JSON serialisation never fails.
    """
    return {
        "name":             record.get("name"),
        "package_name":     record.get("package_name"),
        "package_type":     record.get("package_type"),
        "app_name":         record.get("app_name"),
        "amount":           float(record.get("amount") or 0),
        "discount":         float(record.get("discount") or 0),
        "currency":         record.get("currency") or "INR",
        "payment_status":   record.get("payment_status"),
        "purchase_date":    str(record["purchase_date"]) if record.get("purchase_date") else None,
        "expiry_date":      str(record["expiry_date"]) if record.get("expiry_date") else None,
        "is_active":        bool(record.get("is_active")),
        "sales_invoice_no": record.get("sales_invoice_no"),
    }


@frappe.whitelist()
def get_user_subscription_dashboard():
    """
    Dashboard API — returns subscription summary, active subscription, current
    running plan, and full purchase history for the authenticated user.

    Authentication: Uses frappe.session.user — the frontend must NOT pass an
    email.  The user must be logged in; Guests receive a 403.

    Data sources:
    - Subscription History  → paid purchases (history only)
    - Active Package Details → currently running plan (current_plan + active_subscription)
      This covers base/free packages assigned during onboarding that never
      appear in Subscription History.

    Performance:
    - Two lightweight queries — no N+1, no frappe.get_doc() in loops.
    """

    # ---- Resolve the authenticated user's email --------------------------------
    email = frappe.session.user

    # Block unauthenticated / guest access
    if not email or email == "Guest":
        frappe.throw("Authentication required to access subscription data.", frappe.AuthenticationError)

    # ---- Query 1: currently running package (base / free / paid) ---------------
    # Always fetch this regardless of purchase history so the frontend always
    # knows what plan the user is actually running right now.
    current_plan = _get_current_running_package(email)

    # ---- Query 2: full paid purchase history -----------------------------------
    records = frappe.get_all(
        "Subscription History",
        filters={"customer_email": email},
        fields=_HISTORY_FIELDS,
        order_by="purchase_date desc, name desc",
    )

    # ---- Empty state (no paid history) -----------------------------------------
    if not records:
        return _build_empty_dashboard(current_plan=current_plan)

    # ---- Derive summary --------------------------------------------------------
    summary     = _build_summary(records, current_plan=current_plan)

    # ---- Format history --------------------------------------------------------
    history = [_format_history_item(r) for r in records]

    return {
        "status":              "success",
        "summary":             summary,
        "active_subscription": current_plan,    # always from active package details
        "current_plan":        current_plan,    # always from active package details
        "history":             history,
    }


# ---------------------------------------------------------------------------
# Scheduled Job – Daily Subscription Expiry
# ---------------------------------------------------------------------------
# Runs once per day (registered in hooks.py under scheduler_events["daily"]).
# Finds every Subscription History record where:
#   - is_active == 1
#   - expiry_date is set AND expiry_date < today()
# and sets is_active = 0.
#
# Idempotent: running multiple times has no additional effect.
# Records are never deleted — only deactivated.
# ---------------------------------------------------------------------------

def expire_subscription_history():
    """
    Daily scheduler: automatically deactivate subscriptions whose expiry date
    has passed.

    Logic:
        expiry_date < today()  AND  is_active == 1  →  set is_active = 0
    """
    today_date = getdate(today())

    # Fetch only names to avoid loading full documents.
    expired = frappe.get_all(
        "Subscription History",
        filters={
            "is_active": 1,
            "expiry_date": ["<", today_date],
        },
        pluck="name",
    )

    if not expired:
        # Nothing to do — log is omitted intentionally to keep Error Log clean.
        return

    # Bulk update in one SQL statement — no loops, no N+1.
    try:
        frappe.db.set_value(
            "Subscription History",
            {"is_active": 1, "expiry_date": ["<", today_date]},
            "is_active",
            0,
            update_modified=False,
        )
        frappe.db.commit()

        frappe.log_error(
            title="Subscription Expiry Scheduler - Completed",
            message={
                "expired_count": len(expired),
                "expired_records": expired,
                "run_date": str(today_date),
            },
        )
  
    except Exception:
        frappe.log_error(
            title="Subscription Expiry Scheduler - Error",
            message=frappe.get_traceback(),
        )

@frappe.whitelist(allow_guest=True) 
def initiate_session_booking(payload):
	if isinstance(payload, str):
		data = json.loads(payload)
	else:
		data = payload

	student = data.get("student")
	mentor = data.get("mentor")
	offering = data.get("offering")
	offering_type = data.get("offering_type")
	session_date = data.get("session_date")
	from_time = data.get("from_time")
	to_time = data.get("to_time")
	topic = data.get("topic")
	amount = float(data.get("amount", 0))

	# Create a new Mentor Session Booking document
	doc = frappe.get_doc({
		"doctype": "Mentor Session Booking",
		"student": student,
		"mentor": mentor,
		"offering": offering,
		"offering_type": offering_type,
		"session_date": session_date,
		"from_time": from_time,
		"to_time": to_time,  
		"topic": topic,
		"amount_paid": amount,
		"status": "Payment Pending"
	})  

	# Insert the document safely, ignoring permissions as this is a guest endpoint
	doc.insert(ignore_permissions=True)

	if amount <= 0:
		doc.status = "Pending"
		doc.save(ignore_permissions=True)

		# Create Subscription History for free session
		_create_session_subscription_history(doc, razorpay_payment_id="Free Session")

		return {
			"payment_required": False,
			"booking_id": doc.name
		}

	# For amount > 0, generate Razorpay order remotely on UAT
	try:
		from stridenex_app.api_stridenex_app.uat_client import call_uat_api
		res_order = call_uat_api("quantbit_payments_platform.api.uat_create_razorpay_order", {
			"amount": amount,
			"receipt": doc.name
		})
		order_id = res_order.get("order_id")
		api_key = res_order.get("api_key")
	except Exception as e:
		frappe.delete_doc("Mentor Session Booking", doc.name, ignore_permissions=True, force=True)
		frappe.db.commit()
		frappe.throw(_("Razorpay order creation failed remotely on UAT: {0}").format(str(e)))

	return {
		"payment_required": True,
		"order_id": order_id,
		"api_key": api_key,
		"amount": amount,
		"booking_id": doc.name
	}


@frappe.whitelist(allow_guest=True)
def verify_session_payment(booking_id, razorpay_payment_id, razorpay_order_id, razorpay_signature):
	try:
		from stridenex_app.api_stridenex_app.uat_client import call_uat_api
		verify_res = call_uat_api("quantbit_payments_platform.api.uat_verify_razorpay_signature", {
			"razorpay_order_id": razorpay_order_id,
			"razorpay_payment_id": razorpay_payment_id,
			"razorpay_signature": razorpay_signature
		})
		if not verify_res or verify_res.get("status") != "success":
			err_msg = verify_res.get("error") if verify_res else "Signature verification failed"
			frappe.throw(_("Payment verification failed remotely: {0}").format(err_msg))
	except Exception as e:
		frappe.throw(_("Payment verification failed: Signature mismatch or invalid payment. {0}").format(str(e)))

	try:
		doc = frappe.get_doc("Mentor Session Booking", booking_id)
	except Exception:
		frappe.throw(_("Mentor Session Booking {0} not found.").format(booking_id))

	if doc.status != "Payment Pending":
		frappe.throw(_("Invalid booking status: {0}").format(doc.status))

	doc.status = "Pending"
	doc.payment_reference = razorpay_payment_id
	doc.save(ignore_permissions=True)

	# Create paid Sales Invoice (non-blocking to student flow)
	try:
		from stridenex_app.stridenex_app.doctype.mentor_payout_sheet.mentor_payout_sheet import create_paid_sales_invoice_for_booking
		create_paid_sales_invoice_for_booking(doc, razorpay_payment_id)
	except Exception:
		frappe.log_error(title="Failed to generate Sales Invoice for booking", message=frappe.get_traceback())

	# Create Subscription History for paid session (non-blocking)
	_create_session_subscription_history(doc, razorpay_payment_id=razorpay_payment_id)

	return {
		"success": True,
		"message": "Payment verified successfully.",
		"booking_id": doc.name
	}

def _create_session_subscription_history(doc, razorpay_payment_id):
	"""
	Helper: create a Subscription History entry after a Mentor Session Booking
	is confirmed (paid or free). Wrapped in try/except so any failure is only
	logged — it must never break the user-facing response.
	"""
	try:
		from frappe.utils import today, get_url

		# Resolve customer name from the User doctype
		customer_name = frappe.db.get_value("User", doc.student, "full_name") or doc.student

		# Use topic as the package name, fallback to offering
		package_name = doc.topic or doc.offering or "Session Booking"

		subscription_history = frappe.get_doc({
			"doctype": "Subscription History",
			"customer_email": doc.student,
			"customer_name": customer_name,
			"package_name": package_name,
			"package_type": doc.offering_type or "Session Booking",
			"app_name": "Stridenex App",
			"duration": doc.duration or 0,
			"amount": doc.amount_paid or 0,
			"currency": "INR",
			"discount": 0,
			"payment_status": "Paid",
			"purchase_date": today(),
			"expiry_date": doc.session_date,
			"razorpay_payment_id": razorpay_payment_id,
			"site": get_url(),
			"is_active": 1,
		})
		subscription_history.insert(ignore_permissions=True)
		frappe.db.commit()

	except Exception:
		frappe.log_error(
			title="Session Booking - Subscription History Creation Failed",
			message=frappe.get_traceback()
		)


def cleanup_abandoned_bookings():
	from frappe.utils import now_datetime
	from datetime import timedelta

	cutoff_time = now_datetime() - timedelta(minutes=15)

	abandoned_bookings = frappe.get_all(      
		"Mentor Session Booking",
		filters={
			"status": "Payment Pending",
			"creation": ["<", cutoff_time]
		},   
		pluck="name"
	)

	for booking in abandoned_bookings:
		try:
			frappe.delete_doc("Mentor Session Booking", booking, ignore_permissions=True, force=True)
			frappe.db.commit()
		except Exception as e:
			frappe.log_error(f"Failed to delete abandoned booking {booking}: {str(e)}", "Cleanup Abandoned Bookings")


def get_next_period(last_payout_date, cycle):
	# last_payout_date is the end date of the last processed period.
	# Returns (start_date, end_date) for the next period.
	from frappe.utils import add_days, getdate
	import calendar

	start_date = add_days(last_payout_date, 1)

	if cycle == "Weekly":
		end_date = add_days(last_payout_date, 7)
	elif cycle == "10 Days":
		end_date = add_days(last_payout_date, 10)
	elif cycle == "15 Days":
		end_date = add_days(last_payout_date, 15)
	elif cycle == "20 Days":
		end_date = add_days(last_payout_date, 20)
	elif cycle == "Monthly":
		# Calendar month: next month's last day
		year = start_date.year
		month = start_date.month
		last_day = calendar.monthrange(year, month)[1]
		end_date = start_date.replace(day=last_day)
	else:
		# default/fallback to 30 days
		end_date = add_days(last_payout_date, 30)

	return start_date, end_date


def generate_monthly_payouts():
	"""
	Scheduled task: runs on */1 * * * * (every minute).
	Now fully configurable via Mentor Payout Settings.
	"""
	from frappe.utils import getdate, today, add_days
	import calendar

	# 1. Initialize Mentor Payout Settings if it doesn't exist or is not initialized
	settings = frappe.get_single("Mentor Payout Settings")
	if not settings.last_payout_date:
		settings.payout_cycle = "Monthly"
		settings.last_payout_date = "2026-06-30"  # matching the last month (June 2026)
		settings.set("commission_tiers", [])
		settings.append("commission_tiers", {"threshold": 0.0, "commission_rate": 15.0})
		settings.append("commission_tiers", {"threshold": 50000.0, "commission_rate": 12.0})
		settings.append("commission_tiers", {"threshold": 100000.0, "commission_rate": 10.0})
		settings.save(ignore_permissions=True)
		frappe.db.commit()
		settings = frappe.get_single("Mentor Payout Settings")

	cycle = settings.payout_cycle or "Monthly"
	last_payout_date = getdate(settings.last_payout_date or "2026-06-30")
	today_date = getdate(today())

	# Retrieve commission tiers
	tiers = []
	for tier in settings.get("commission_tiers") or []:
		tiers.append({
			"threshold": float(tier.threshold or 0),
			"rate": float(tier.commission_rate or 0) / 100.0
		})

	if not tiers:
		tiers = [
			{"threshold": 0.0, "rate": 0.15},
			{"threshold": 50000.0, "rate": 0.12},
			{"threshold": 100000.0, "rate": 0.10}
		]

	# Sort tiers by threshold ascending
	tiers = sorted(tiers, key=lambda x: x["threshold"])

	# Process any fully completed periods
	while True:
		start_date, end_date = get_next_period(last_payout_date, cycle)
		if today_date <= end_date:
			# Current period has not completed yet
			break

		if cycle == "Monthly":
			month_year_label = end_date.strftime("%B %Y")
		else:
			month_year_label = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"

		# Check if there are any unpaid bookings for this period
		bookings_exist = frappe.db.exists(
			"Mentor Session Booking",
			{
				"payout_status": "Unpaid",
				"session_date": ["between", [str(start_date), str(end_date)]]
			}
		)

		if bookings_exist:
			try:
				# Create the new comprehensive Mentor Payout Sheet
				sheet = frappe.get_doc({
					"doctype": "Mentor Payout Sheet",
					"payout_cycle": cycle,
					"start_date": start_date,
					"end_date": end_date
				})
				
				# The validate() method inside Mentor Payout Sheet automatically
				# populates the mentors, sessions, penalties, and summary tables.
				sheet.insert(ignore_permissions=True)
				frappe.db.commit()

			except Exception:
				frappe.log_error(
					title=f"Payout Sheet Generation Error for period {month_year_label}",
					message=frappe.get_traceback(),
				)
				frappe.db.rollback()

		# Update last_payout_date and commit progress for this period
		last_payout_date = end_date
		frappe.db.set_value("Mentor Payout Settings", "Mentor Payout Settings", "last_payout_date", last_payout_date)
		frappe.db.commit()


@frappe.whitelist(allow_guest=True)
def get_mentor_dashboard_data(mentor_email):
	if not mentor_email:
		frappe.throw("mentor_email is required")

	# ── helpers ──────────────────────────────────────────────────────────────
	def _fmt(amount):
		"""Format a numeric amount as ₹1,23,456 (Indian comma style)."""
		try:
			amount = float(amount or 0)
		except (ValueError, TypeError):
			amount = 0.0

		# Split into integer and decimal parts
		is_negative = amount < 0
		amount = abs(amount)
		int_part = int(amount)
		dec_part = round((amount - int_part) * 100)

		# Indian grouping: last 3 digits, then groups of 2
		s = str(int_part)
		if len(s) > 3:
			last3 = s[-3:]
			rest  = s[:-3]
			groups = []
			while rest:
				groups.append(rest[-2:])
				rest = rest[:-2]
			s = ",".join(reversed(groups)) + "," + last3
		formatted = f"₹{s}" if dec_part == 0 else f"₹{s}.{dec_part:02d}"
		return f"-{formatted}" if is_negative else formatted

	def _fmt_date(d):
		"""Return 'Mon D, YYYY' string or 'TBD' if date is falsy."""
		if not d:
			return "TBD"
		try:
			from frappe.utils import getdate
			dt = getdate(d)
			return dt.strftime("%b %-d, %Y")
		except Exception:
			return "TBD"

	# ── fetch all payout records for this mentor ──────────────────────────────
	# Now using the comprehensive Mentor Payout Sheet architecture
	records = frappe.db.sql("""
		SELECT 
			child.name,
			child.total_sessions,
			child.gross_amount,
			child.commission_rate,
			child.commission_amount,
			child.net_payout,
			parent.end_date as payment_date,
			CASE WHEN parent.docstatus = 1 THEN 'Paid' ELSE 'Processing' END as status
		FROM `tabMentor Payout Sheet Row` child
		JOIN `tabMentor Payout Sheet` parent ON child.parent = parent.name
		WHERE child.mentor = %s AND child.released = 1
		ORDER BY parent.end_date DESC
	""", (mentor_email,), as_dict=True)

	for r in records:
		if r.payment_date:
			from frappe.utils import getdate
			r.month_year = getdate(r.payment_date).strftime("%B %Y")
		else:
			r.month_year = "TBD"

	# ── lifetime aggregates ───────────────────────────────────────────────────
	lifetime_gross      = sum(float(r.gross_amount      or 0) for r in records)
	lifetime_commission = sum(float(r.commission_amount or 0) for r in records)
	lifetime_net        = sum(float(r.net_payout        or 0) for r in records)

	# ── summary stats ─────────────────────────────────────────────────────────
	pending_payout = sum(
		float(r.net_payout or 0) for r in records if r.status == "Processing"
	)

	paid_records = [r for r in records if r.status == "Paid"]
	last_paid    = float(paid_records[0].net_payout or 0) if paid_records else 0.0

	# ── history array ─────────────────────────────────────────────────────────
	history = []
	for r in records:
		gross      = float(r.gross_amount      or 0)
		commission = float(r.commission_amount or 0)
		net        = float(r.net_payout        or 0)
		rate       = float(r.commission_rate   or 0)

		history.append({
			"month":      r.month_year,
			"sessions":   int(r.total_sessions or 0),
			"gross_raw":  gross,
			"gross":      _fmt(gross),
			"feePercent": f"{int(rate)}%",
			"feeAmount":  _fmt(-commission),       # formatted as negative e.g. -₹3,240
			"net_raw":    net,
			"net":        _fmt(net),
			"status":     r.status,
			"date":       _fmt_date(r.payment_date),
		})

	# ── Live Current Period (Unprocessed) ──────────────────────────────────────
	from frappe.utils import today, get_first_day, get_last_day, getdate

	try:
		settings = frappe.get_single("Mentor Payout Settings")
		cycle = settings.payout_cycle or "Monthly"
		last_payout_date = getdate(settings.last_payout_date or "2026-06-30")
		current_start, current_end = get_next_period(last_payout_date, cycle)
	except Exception:
		current_date = today()
		current_start = get_first_day(current_date)
		current_end = get_last_day(current_date)

	unprocessed_sessions = frappe.get_all(
		"Mentor Session Booking",
		filters={
			"mentor": mentor_email,
			"status": "Completed",
			"payout_status": "Unpaid",
			"session_date": ["between", [str(current_start), str(current_end)]]
		},
		fields=["amount_paid"]
	)

	current_gross = sum(float(s.amount_paid or 0) for s in unprocessed_sessions)

	# Estimate live net payout based on tiers
	try:
		tiers = []
		for tier in settings.get("commission_tiers") or []:
			tiers.append({
				"threshold": float(tier.threshold or 0),
				"rate": float(tier.commission_rate or 0) / 100.0
			})
		if not tiers:
			tiers = [
				{"threshold": 0.0, "rate": 0.15},
				{"threshold": 50000.0, "rate": 0.12},
				{"threshold": 100000.0, "rate": 0.10}
			]
		tiers = sorted(tiers, key=lambda x: x["threshold"])
	except Exception:
		tiers = [
			{"threshold": 0.0, "rate": 0.15},
			{"threshold": 50000.0, "rate": 0.12},
			{"threshold": 100000.0, "rate": 0.10}
		]

	current_rate = 0.15
	for tier in tiers:
		if current_gross >= tier["threshold"]:
			current_rate = tier["rate"]

	current_net = current_gross - (current_gross * current_rate)  

	return {
		"lifetime": {
			"gross":      _fmt(lifetime_gross),
			"commission": _fmt(lifetime_commission),
			"net":        _fmt(lifetime_net),
		},
		"summary": {
			"pending_payout":     _fmt(pending_payout),
			"last_paid":          _fmt(last_paid),
			"current_month_live": _fmt(current_net)
		},
		"history": history,
	}

