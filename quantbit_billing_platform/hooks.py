app_name = "quantbit_billing_platform"
app_title = "Quantbit Billing Platform"
app_publisher = "Quantbit Technologies Pvt Ltd"
app_description = "This platform is designed to manage and automate customer billing based on platform usage, API consumption, and service parameters. It acts as a centralized configuration system that connects external customer platforms with the internal billing application."
app_email = "support@quantbit.io"
app_license = "mit"

# Apps
# ------------------

# on_login = "quantbit_billing_platform.quantbit_billing_platform.doctype.billing_account_master.billing_account_master."
# boot_session = "quantbit_billing_platform.quantbit_billing_platform.api.custom_boot_session"
# boot_session = "quantbit_billing_platform.quantbit_billing_platform.doctype.billing_account_master.billing_account_master.set_default_company_boot"



doc_events = {
    "*": {
        "after_insert": [
            "quantbit_billing_platform.quantbit_billing_platform.token_logic.consume_tokens",
            "quantbit_billing_platform.quantbit_billing_platform.doctype.billing_email_setting.billing_email_setting.handle_doc_event"
        ],

        "on_update": [
            "quantbit_billing_platform.quantbit_billing_platform.token_logic.consume_tokens",
            "quantbit_billing_platform.quantbit_billing_platform.doctype.billing_email_setting.billing_email_setting.handle_doc_event"
        ],

        "on_submit": [
            "quantbit_billing_platform.quantbit_billing_platform.doctype.billing_email_setting.billing_email_setting.handle_doc_event"
        ],

        "on_cancel": [
            "quantbit_billing_platform.quantbit_billing_platform.doctype.billing_email_setting.billing_email_setting.handle_doc_event"
        ],

        "validate": [
            "quantbit_billing_platform.quantbit_billing_platform.doctype.billing_email_setting.billing_email_setting.handle_doc_event"
        ]
    },
    "Billing Account Master": {
        "before_save": [
            "quantbit_billing_platform.quantbit_billing_platform.api.allocate_package_quotas"
        ]
    }
}






fixtures = [
	{
        "dt": "Website Settings"
    },

	{
		"doctype": "Custom HTML Block",
		"filters": [
			["name", "in", ["Pay Button", "User Package Info","Plans Dashboard","Payment Invoices Dashboard"]]
		]
	},

    
    {
        "doctype": "Print Format",
        "filters": [
            ["name", "in", ["Payment Invoice Details"]]
        ]
    },

	{
		"doctype": "Billing Role",
		"filters": [
			["name", "=", "User Role"]
		]
	},
    {

        "doctype":"Billing Role Permission Setting",
        "filters":[
            ["name", "=", "User Role"]
        ]
    },
    {
        "dt": "Custom DocPerm",
        "filters": [
            ["parent", "in", [
                "Billing Account Master",
                "Billing Package",
                "Billing Package Ledger",
                "Billing Module Configuration",
                "Billing Notification",
                "Billing Role",
                "Role",
                "User",
                "Billing Role Permission Setting",
                "Billing Settings",
                "Active Package Details",
                "Application Feature"
            ]]
        ]
    },
    {
    "doctype": "Workspace",
        "filters": [
            ["name", "in", ["Quantbit Billing Platform","Projects", "Support","Website","CRM","ERPNext Integrations","Home","Accounting","HR","Manufacturing","Retail","Quality","Users","Build","Tools","Erpnext Settings","Custom","Developer","Integrations","Accounts","Assets","Buying","Selling","Stock","Services","Contacts"]]
        ]
    },
]



scheduler_events = {
	"cron": {
		"*/1 * * * *": [
			"quantbit_billing_platform.quantbit_billing_platform.api.expire_billing_packages",
			"quantbit_billing_platform.quantbit_billing_platform.api.send_notification_to_user",
            "quantbit_billing_platform.quantbit_billing_platform.api.expire_token_on_date",
            "quantbit_billing_platform.quantbit_billing_platform.api.cleanup_abandoned_bookings",
            "quantbit_billing_platform.quantbit_billing_platform.api.generate_monthly_payouts"
		]
		,
		# Runs at 02:00 AM on the 1st of every month
		# "0 2 1 * *": [
		# 	"quantbit_billing_platform.quantbit_billing_platform.api.generate_monthly_payouts"
		# ]
	},
    "daily": [
        "quantbit_billing_platform.quantbit_billing_platform.doctype.billing_email_setting.billing_email_setting.run_date_based_emails",
        "quantbit_billing_platform.quantbit_billing_platform.api.expire_subscription_history",
        "quantbit_billing_platform.quantbit_billing_platform.doctype.billing_email_setting.billing_email_setting.send_package_expiry_reminders"
    ]
	# "daily": [
	#     "quantbit_billing_platform.quantbit_billing_platform.api.send_notification_to_user",
	# ]
}


# Include JS and CSS globally in the Desk
app_include_js = "/assets/quantbit_billing_platform/js/global_notification_bar.js"
app_include_css = "/assets/quantbit_billing_platform/css/global_notification_bar.css"







# include js, css files in header of desk.html
# app_include_css = "/assets/quantbit_billing_platform/css/quantbit_billing_platform.css"
# app_include_js = "/assets/quantbit_billing_platform/js/quantbit_billing_platform.js"

# include js, css files in header of web template
# web_include_css = "/assets/quantbit_billing_platform/css/quantbit_billing_platform.css"
# web_include_js = "/assets/quantbit_billing_platform/js/quantbit_billing_platform.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "quantbit_billing_platform/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "quantbit_billing_platform/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "quantbit_billing_platform.utils.jinja_methods",
# 	"filters": "quantbit_billing_platform.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "quantbit_billing_platform.install.before_install"
after_install = "quantbit_billing_platform.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "quantbit_billing_platform.uninstall.before_uninstall"
# after_uninstall = "quantbit_billing_platform.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "quantbit_billing_platform.utils.before_app_install"
# after_app_install = "quantbit_billing_platform.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "quantbit_billing_platform.utils.before_app_uninstall"
# after_app_uninstall = "quantbit_billing_platform.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "quantbit_billing_platform.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------




# scheduler_events = {
# 	"all": [
# 		"quantbit_billing_platform.tasks.all"
# 	],
# 	"daily": [
# 		"quantbit_billing_platform.tasks.daily"
# 	],
# 	"hourly": [  
# 		"quantbit_billing_platform.tasks.hourly"
# 	],
# 	"weekly": [
# 		"quantbit_billing_platform.tasks.weekly"
# 	],
# 	"monthly": [
# 		"quantbit_billing_platform.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "quantbit_billing_platform.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "quantbit_billing_platform.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "quantbit_billing_platform.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["quantbit_billing_platform.utils.before_request"]
# after_request = ["quantbit_billing_platform.utils.after_request"]

# Job Events
# ----------
# before_job = ["quantbit_billing_platform.utils.before_job"]
# after_job = ["quantbit_billing_platform.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"quantbit_billing_platform.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

