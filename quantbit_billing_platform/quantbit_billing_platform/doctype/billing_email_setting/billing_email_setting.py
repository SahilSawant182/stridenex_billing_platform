# Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, getdate, nowdate
import re


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_allowed_doctypes(doctype, txt, searchfield, start, page_len, filters):

    return frappe.db.sql("""
        SELECT name
        FROM `tabDocType`
        WHERE
            istable = 0
        AND (
            module = 'Quantbit Billing Platform'
            OR name = 'User'
        )
        AND name LIKE %(txt)s
        ORDER BY name
        LIMIT 50
    """, {
        "txt": f"%{txt}%"
    })


def handle_doc_event(doc, method):

    rule_names = frappe.get_all(
        "Billing Email Setting",
        filters={
            "doctype_name": doc.doctype,
            "enable": 1
        },
        pluck="name"
    )

    for rule_name in rule_names:

        rule_doc = frappe.get_doc("Billing Email Setting", rule_name)

        if rule_doc.event == "Save" and method in ["after_insert", "on_update"]:
            send_dynamic_email(rule_doc, doc)

        elif rule_doc.event == "Submit" and method == "on_submit":
            send_dynamic_email(rule_doc, doc)

        elif rule_doc.event == "Cancel" and method == "on_cancel":
            send_dynamic_email(rule_doc, doc)

        elif rule_doc.event == "Validate":
            if check_validation_condition(rule_doc, doc):
                send_dynamic_email(rule_doc, doc)



def check_validation_condition(rule, doc):

    field_value = doc.get(rule.field_name)

    if rule.validation_type == "Has Value":

        return bool(field_value)

    if rule.validation_type == "Is Null/None":

        return not bool(field_value)

    if rule.validation_type == "On Change":

        if not doc.is_new():

            previous_doc = doc.get_doc_before_save()

            if previous_doc:

                old_value = previous_doc.get(rule.field_name)

                return old_value != field_value

    return False


def parse_template(template_text, rule, doc):

    if not template_text:
        return ""

    content = template_text

    placeholders = re.findall(r"\{(.*?)\}", content)

    mapping = {}

    for row in rule.template_values:

        if row.name1 and row.select_field:

            mapping[row.name1.strip().lower()] = row.select_field.strip()

    for placeholder in placeholders:

        fieldname = mapping.get(placeholder.strip().lower())

        if fieldname:

            value = doc.get(fieldname) or ""

            content = content.replace(
                f"{{{placeholder}}}",
                str(value)
            )

    return content


def send_dynamic_email(rule, doc):

    frappe.log_error(
            message=f"""
        DocType: {doc.doctype}
        DocName: {doc.name}
        Data: {doc.as_dict()}
        """,
            title="Billing Email Engine Debug"
        )

    subject = parse_template(rule.subject, rule, doc)
    message = parse_template(rule.template, rule, doc)

    recipient = doc.email if doc.doctype == "User" else frappe.session.user

    # final safety check
    if not recipient:
        frappe.log_error(
            title="Billing Email Setting Error",
            message=f"No recipient found for document {doc.name}"
        )
        return

    frappe.sendmail(
        recipients=[recipient],
        subject=subject,
        message=message
    )


def run_date_based_emails():

    today = getdate(nowdate())

    rules = frappe.get_all(
        "Billing Email Setting",
        filters={
            "event": "Days",
            "enable": 1
        },
        pluck="name"
    )

    for rule in rules:

        rule_doc = frappe.get_doc(
            "Billing Email Setting",
            rule.name
        )

        docs = frappe.get_all(
            rule_doc.doctype_name,
            fields=["name", "creation"]
        )

        for d in docs:

            target_doc = frappe.get_doc(
                rule_doc.doctype_name,
                d.name
            )

            target_date = None


            if rule_doc.type == "On Create":

                target_date = add_days(
                    getdate(target_doc.creation),
                    rule_doc.day
                )


            elif rule_doc.type in ["Before", "After"]:

                if rule_doc.days_validate_on == "On Doctype Field":

                    base_date = target_doc.get(
                        rule_doc.field_name
                    )

                else:

                    base_date = rule_doc.date

                if not base_date:

                    continue

                if rule_doc.type == "Before":

                    target_date = add_days(
                        getdate(base_date),
                        -rule_doc.day
                    )

                else:

                    target_date = add_days(
                        getdate(base_date),
                        rule_doc.day
                    )

            if target_date == today:

                send_dynamic_email(
                    rule_doc,
                    target_doc
                )


class BillingEmailSetting(Document):
	pass



# apps/quantbit_billing_platform/quantbit_billing_platform/tasks.py

import frappe
from frappe.utils import today, add_days, getdate, cint

def send_package_expiry_reminders():
    """
    Daily scheduled job.
    Checks Active Package Details for records where to_date is
    5, 3, 2, or 1 day(s) from today and sends a reminder email.
    """
    reminder_days = [5, 3, 2, 1]
    current_date = getdate(today())

    for days in reminder_days:
        target_date = add_days(current_date, days)

        packages = frappe.get_all(
            "Active Package Details",
            filters={
                "to_date": target_date
            },
            fields=[
                "name", "user", "app_name", "billing_package",
                "package_type", "to_date", "remaining_tokens",
                "total_tokens", "no_of_days"
            ]
        )

        for pkg in packages:
            send_reminder_email(pkg, days)


def send_reminder_email(pkg, days_remaining):
    user_email = pkg.get("user")
    if not user_email:
        return

    # Avoid duplicate sends if job runs more than once a day
    flag_field = f"reminder_sent_{days_remaining}"
    already_sent = frappe.db.get_value(
        "Active Package Details", pkg["name"], flag_field
    ) if frappe.db.has_column("Active Package Details", flag_field) else None

    if already_sent:
        return

    subject = f"Your {pkg.get('app_name') or 'Subscription'} plan expires in {days_remaining} day(s)"

    message = f"""
        <p>Dear User,</p>
        <p>Your subscription package <b>{pkg.get('billing_package')}</b>
        ({pkg.get('package_type')}) for <b>{pkg.get('app_name')}</b>
        is expiring on <b>{frappe.utils.formatdate(pkg.get('to_date'))}</b>
        ({days_remaining} day(s) remaining).</p>
        <p>Remaining Tokens: <b>{pkg.get('remaining_tokens')}</b> / {pkg.get('total_tokens')}</p>
        <p>Please renew or upgrade your plan to continue uninterrupted access.</p>
        <p><a href="{frappe.utils.get_url()}/app/active-package-details/{pkg.get('name')}">
        Click here to renew/upgrade</a></p>
        <p>Regards,<br>Team</p>
    """

    try:
        frappe.sendmail(
            recipients=[user_email],
            subject=subject,
            message=message,
            reference_doctype="Active Package Details",
            reference_name=pkg.get("name"),
        )
        frappe.logger().info(f"Reminder email sent to {user_email} for {pkg.get('name')} ({days_remaining} days left)")

        if frappe.db.has_column("Active Package Details", flag_field := f"reminder_sent_{days_remaining}"):
            frappe.db.set_value("Active Package Details", pkg["name"], flag_field, 1)

    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"Failed to send package expiry reminder for {pkg.get('name')}"
        )
