# Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe


from frappe.model.document import Document
import frappe
import random


class EmailOTPVerification(Document):
    def before_save(self):
        if not self.otp_send:  # only generate if empty
            self.otp_send = random.randint(100000, 999999)
            self.verified = 0


@frappe.whitelist()
def send_otp(email_id):
    otp = random.randint(100000, 999999)

    doc_name = frappe.db.get_value(
        "Email OTP Verification",
        {"email_id": email_id},
        "name"
    )

    if doc_name:
        doc = frappe.get_doc("Email OTP Verification", doc_name)
    else:
        doc = frappe.new_doc("Email OTP Verification")
        doc.email_id = email_id

    doc.otp_send = otp
    doc.verified = 0
    doc.save(ignore_permissions=True)

    frappe.sendmail(
        recipients=[email_id],
        subject="Your OTP Code",
        message=f"Your OTP is {otp}"
    )

    return "OTP Sent"


@frappe.whitelist()
def verify_otp(email_id, user_otp):
    doc_name = frappe.db.get_value(
        "Email OTP Verification",
        {"email_id": email_id},
        "name"
    )

    if not doc_name:
        return "No record found"

    doc = frappe.get_doc("Email OTP Verification", doc_name)

    if str(doc.otp_send) == str(user_otp):
        doc.verified = 1
        doc.save(ignore_permissions=True)
        return "Verified"
    else:
        return "Invalid OTP"


@frappe.whitelist(allow_guest=True)
def create_update_and_send_otp(email):
    try:
        frappe.log_error(f"API called with email: {email}", "DEBUG")

        doc_name = frappe.db.get_value(
            "Email OTP Verification",
            {"email_id": email},
            "name"
        )

        frappe.log_error(f"Doc found: {doc_name}", "DEBUG")

        if doc_name:
            doc = frappe.get_doc("Email OTP Verification", doc_name)
        else:
            doc = frappe.new_doc("Email OTP Verification")

        doc.email_id = email
        doc.otp_send = random.randint(100000, 999999)
        doc.verified = 0

        doc.save(ignore_permissions=True)
        frappe.db.commit()

        frappe.sendmail(
            recipients=[email],
            subject="Your OTP Code",
            message=f"Your OTP for verification is {doc.otp_send}",
            now=True  
        )

        frappe.log_error("Email sent successfully", "DEBUG")

        return {
            "message": "Updated & Email Sent" if doc_name else "Created & Email Sent",
            "name": doc.name,
            "email": doc.email_id
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "ERROR in create_update_and_send_otp")
        return {"status": False, "message": str(e)}





@frappe.whitelist(allow_guest=True)
def check_email_otp(email, otp):
    # Check matching record
    doc_name = frappe.db.get_value(
        "Email OTP Verification",
        {
            "email_id": email,
            "otp_send": otp
        },
        "name"
    )

    if doc_name:
        # ✅ Match found → set verified = 1
        doc = frappe.get_doc("Email OTP Verification", doc_name)
        doc.verified = 1
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": True,
            "message": "Match Found & Verified"
        }
    else:
        # ❌ No match → set verified = 0 for that email (if exists)
        email_doc_name = frappe.db.get_value(
            "Email OTP Verification",
            {"email_id": email},
            "name"
        )

        if email_doc_name:
            doc = frappe.get_doc("Email OTP Verification", email_doc_name)
            doc.verified = 0
            doc.save(ignore_permissions=True)
            frappe.db.commit()

        return {
            "status": False,
            "message": "OTP Invalid"
        }



@frappe.whitelist()
def clean_email_otp_records():
    otp_records = frappe.get_all(
        "Email OTP Verification",
        fields=["name", "email_id"]
    )

    for record in otp_records:
        # Match with Billing Account Master.email
        exists = frappe.db.exists(
            "Billing Account Master",
            {"email": record.email_id}
        )

        if exists:
            # ❌ Delete matching email from OTP doctype
            frappe.delete_doc(
                "Email OTP Verification",
                record.name,
                ignore_permissions=True
            )

    frappe.db.commit()

    return "Cleanup Completed Successfully"
