import frappe

@frappe.whitelist(allow_guest=True)
def get_installed_apps():
    try:
        installed_app_names = frappe.get_installed_apps()
        if not installed_app_names:
            return {"message": "success", "data": []}

        excluded_apps = {"frappe", "erpnext"}
        apps = []

        for app_name in installed_app_names:
            if app_name in excluded_apps:
                continue

            try:
                # Try to get nice title and icon from hooks
                app_title_hooks = frappe.get_hooks("app_title", app_name=app_name) or []
                app_icon_hooks = frappe.get_hooks("app_icon", app_name=app_name) or []

                title = app_title_hooks[0] if app_title_hooks else app_name.replace("_", " ").title()
                icon = app_icon_hooks[0] if app_icon_hooks else "fas fa-cube"  # better default fallback

                apps.append({
                    "name": app_name,
                    "title": title,
                    "icon": icon,
                    "shortDesc": f"{title} Module",  # you can make this smarter later
                })
            except Exception:
                # Minimal fallback
                apps.append({
                    "name": app_name,
                    "title": app_name.replace("_", " ").title(),
                    "icon": "fas fa-cube",
                    "shortDesc": "Custom Application",
                })

        apps.sort(key=lambda x: x["title"].lower())
        return {"message": "success", "data": apps}

    except Exception as e:
        frappe.log_error(f"Error in get_installed_apps: {str(e)}")
        return {"message": "error", "error": str(e)}


@frappe.whitelist(allow_guest=True)
def get_billing_modules():
    try:
        docs = frappe.get_all(
            "Billing Module Configuration",
            fields=[
                "name",
                "app",
                "app_subtitle as subtitle",
                "app_short_description as short_description",
                
                "app_image_url as image_url",
                "app_description as description",
                
            ],
            order_by="app asc"
        )

        result = []
        for doc in docs:
            # Fetch child table features separately
            features = frappe.get_all(
                "App Feature Details",
                filters={"parent": doc.name, "parenttype": "Billing Module Configuration"},
                fields=["feature_list"],
                pluck="feature_list"   # returns simple list
            )

            result.append({
                "name": doc.name,
                "app": doc.app,
                "title": doc.name.replace("_", " ").title(),
                "subtitle": doc.subtitle or "",
                "short_description": doc.short_description or "",
                "icon": doc.icon or "fas fa-cube",
                "image_url": doc.image_url or "",
                "description": doc.description or "No description available.",
                "features": features or []
            })

        return {"message": "success", "data": result}

    except Exception as e:
        frappe.log_error("get_billing_modules failed", str(e))
        return {"message": "error", "error": str(e)}


import frappe

@frappe.whitelist(allow_guest=True)
def get_app_details(app_name):
    try:
        # Fetch parent document
        doc = frappe.get_all(
            "Billing Module Configuration",
            filters={"name": app_name},
            fields=[
                "name",
                "app_subtitle",
                "app_description",
                "app_image_url"
            ],
            limit=1
        )

        if not doc:
            return {"message": "error", "error": "App not found"}

        doc = doc[0]

        # Fetch features
        features = frappe.get_all(
            "App Feature Details",
            filters={"parent": doc.name},
            fields=["feature_list"],
            pluck="feature_list",
            order_by="idx asc"
        )

        return {
            "message": "success",
            "data": {
                "title": doc.name,
                "subtitle": doc.app_subtitle or "",
                "description": doc.app_description or "",
                "image_url": doc.app_image_url or "",
                "features": features
            }
        }

    except frappe.PermissionError:
        return {"message": "error", "error": "Permission denied"}
    except Exception as e:
        frappe.log_error("get_app_details failed", str(e))
        return {"message": "error", "error": str(e)}
    


@frappe.whitelist(allow_guest=True)
def redirect_to_portal():
    billing_settings = frappe.get_single("Billing Settings")

    sys_url = billing_settings.sys_url or ""
    commission = billing_settings.partners_commission_rate or 0

    return {
        "url": f"{sys_url}/partner-portal",
        "partners_commission_rate": commission
    }