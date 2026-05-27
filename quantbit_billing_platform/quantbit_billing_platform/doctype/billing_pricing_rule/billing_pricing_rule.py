# Copyright (c) 2026, Quantbit Technologies Pvt Ltd
# License: MIT

import frappe
import requests
from requests.auth import HTTPBasicAuth
from frappe.model.document import Document


class BillingPricingRule(Document):

	def on_trash(self):
		self.sync_delete_pricing_rule()

	def before_save(self):

		settings = frappe.get_single("Billing Settings")

		if not settings.sys_url:
			frappe.throw("System URL missing in Billing Settings")

		# ✅ Using Billing User + Password
		if not settings.billing_user or not settings.billing_user_password:
			frappe.throw("Billing User credentials missing")

		remote_url = settings.sys_url.rstrip("/")

		endpoint = (
			f"{remote_url}/api/method/"
			"quantbit_payments_platform.api.sync_pricing_rule"
		)

		payload = {
			"name": self.name,
			"title": self.title,
			"apply_on": self.apply_on,
			"rate_or_discount": self.rate_or_discount,
			"discount_percentage": self.discount_percentage,
			"valid_from": str(self.valid_from) if self.valid_from else None,
			"valid_upto": str(self.valid_upto) if self.valid_upto else None,

			# REQUIRED ERPNext fields
			"selling": self.selling,
			"buying": self.buying,
		}

		# Remove None values
		payload = {
			k: v for k, v in payload.items()
			if v is not None
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
					f"Pricing Rule sync failed: {response.text}"
				)

			result = response.json()

			if result.get("message") != "success":
				frappe.throw(
					f"Remote sync error: {result}"
				)

		except requests.exceptions.RequestException as e:

			frappe.throw(
				f"Pricing Rule sync failed: {str(e)}"
			)

	def sync_delete_pricing_rule(self):

		settings = frappe.get_single("Billing Settings")

		if not settings.sys_url:
			return

		# ✅ Using Billing User + Password
		if not settings.billing_user or not settings.billing_user_password:
			return

		remote_url = settings.sys_url.rstrip("/")

		endpoint = (
			f"{remote_url}/api/method/"
			"quantbit_payments_platform.api.delete_pricing_rule"
		)

		payload = {
			"pricing_rule": self.name
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
			response = requests.session.post(
				endpoint,
				json=payload,
				headers={
					"Content-Type": "application/json"
				},
				timeout=10
			)
			if response.status_code != 200:
				frappe.log_error(
					response.text,
					"Pricing Rule Delete Sync Failed"
				)
				return

			result = response.json()

			if result.get("message") != "success":
				frappe.log_error(
					str(result),
					"Pricing Rule Delete Sync Failed"
				)

		except requests.exceptions.RequestException as e:

			frappe.log_error(
				str(e),
				"Pricing Rule Delete Sync Failed"
			)