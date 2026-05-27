# Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
import requests
from requests.auth import HTTPBasicAuth
from frappe.model.document import Document


class BillingCouponCode(Document):

	def on_trash(self):
		self.sync_delete_coupon()

	def before_save(self):

		settings = frappe.get_single("Billing Settings")

		if not settings.sys_url:
			frappe.throw("System URL not configured in Billing Settings")

		# ✅ Using Billing User + Password now
		if not settings.billing_user or not settings.billing_user_password:
			frappe.throw(
				"Billing User credentials missing in Billing Settings"
			)

		remote_url = settings.sys_url.rstrip("/")

		current_site = (
			settings.current_site_url.rstrip("/")
			if settings.current_site_url
			else frappe.utils.get_url()
		)

		endpoint = (
			f"{remote_url}/api/method/"
			"quantbit_payments_platform.api.sync_coupon_code"
		)

		payload = {
			"name": self.coupon_code,
			"coupon_name": self.coupon_code,
			"custom_site": current_site,
			"coupon_code": self.coupon_code,
			"coupon_type": self.coupon_type,
			"valid_from": str(self.valid_from) if self.valid_from else None,
			"valid_upto": str(self.valid_upto) if self.valid_upto else None,
			"maximum_use": self.maximum_use,
			"pricing_rule": self.pricing_rule,
			"description": self.description
		}

		try:

			session = requests.Session()

			# Login
			login_response = session.post(
				f"{remote_url}/api/method/login",
				data={
					"usr": settings.billing_user,
					"pwd": settings.billing_user_password
				},
				timeout=10
			)

			if login_response.status_code != 200:
				frappe.throw(
					f"Remote login failed: {login_response.text}"
				)

			# Actual API Call
			response = session.post(
				endpoint,
				json=payload,
				headers={
					"Content-Type": "application/json"
				},
				timeout=10
			)

			if response.status_code != 200:
				frappe.throw(
					f"Remote sync failed: {response.text}"
				)

			result = response.json()

			if result.get("message") != "success":
				frappe.throw(
					f"Remote sync error: {result}"
				)

		except requests.exceptions.RequestException as e:

			frappe.throw(
				f"Coupon sync failed with remote system: {str(e)}"
			)

	def sync_delete_coupon(self):

		settings = frappe.get_single("Billing Settings")

		if not settings.sys_url:
			return

		# ✅ Using Billing User + Password now
		if not settings.billing_user or not settings.billing_user_password:
			return

		remote_url = settings.sys_url.rstrip("/")

		endpoint = (
			f"{remote_url}/api/method/"
			"quantbit_payments_platform.api.delete_coupon_code"
		)

		payload = {
			"coupon_code": self.coupon_code
		}

		try:

			session = requests.Session()

			# Login
			login_response = session.post(
				f"{remote_url}/api/method/login",
				data={
					"usr": settings.billing_user,
					"pwd": settings.billing_user_password
				},
				timeout=10
			)

			if login_response.status_code != 200:
				frappe.throw(
					f"Remote login failed: {login_response.text}"
				)

			# Actual API Call
			response = session.post(
				endpoint,
				json=payload,
				headers={
					"Content-Type": "application/json"
				},
				timeout=10
			)

			if response.status_code != 200:
				frappe.throw(
					f"Remote delete failed: {response.text}"
				)

			result = response.json()

			if result.get("message") != "success":
				frappe.throw(
					f"Remote delete error: {result}"
				)

		except requests.exceptions.RequestException as e:

			frappe.throw(
				f"Coupon delete sync failed: {str(e)}"
			)