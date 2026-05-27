# Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.password import update_password
from frappe.utils import today, add_days, date_diff
from quantbit_billing_platform.utils import generate_random_id

# Session Defoult company set on login
def set_session_company(login_manager):

	user = frappe.session.user

	if user == "Guest":
		return

	company = frappe.db.get_value(
		"Billing Account Master",
		{"email": user},
		"company"
	)

	if not company:
		return

	frappe.defaults.set_user_default("company", company, user)

	if not frappe.db.exists(
		"User Permission",
		{
			"user": user,
			"allow": "Company",
			"for_value": company
		}
	):
		perm = frappe.get_doc({
			"doctype": "User Permission",
			"user": user,
			"allow": "Company",
			"for_value": company,
			"apply_to_all_doctypes": 1
		})
		perm.insert(ignore_permissions=True)

	frappe.db.commit()


#session defoult company set on boot
def set_default_company_boot(bootinfo):
	user = frappe.session.user
	if user == "Guest":
		return

	company = frappe.db.get_value(
		"Billing Account Master",
		{"email": user},
		"company"
	)

	if not company:
		return

	frappe.defaults.set_user_default("company", company, user)

	if "user_defaults" not in bootinfo:
		bootinfo["user_defaults"] = {}

	bootinfo["user_defaults"]["company"] = company


class BillingAccountMaster(Document):

	def before_insert(self):
		if self.company_name:
			self.company = self.company_name

		if self.flags.from_child_creation:
			self.is_master_user = 0
		else:
			self.is_master_user = 1

		
  
	def after_insert(self):
		self.sync_company()
		self.sync_users()


	def before_save(self):

		#check for duplicate apps in billing details
		apps = []

		for row in self.billing_details:

			if row.app_name in apps:
				frappe.throw(f"App {row.app_name} already exists in Billing Details.")

			apps.append(row.app_name)

		# Validate user limit per app
		allowed_users_per_app = {}

		#Get allowed users from billing_details
		for row in self.billing_details:

			if not row.billing_package or not row.app_name:
				continue
  
			package_doc = frappe.get_doc("Billing Package", row.billing_package)

			allowed_users_per_app[row.app_name] = package_doc.no_of_users or 0


		#Count users created per app
		users_per_app = {}
		for row in self.billing_user_detail:
			if not row.app_name:
				continue
			users_per_app[row.app_name] = users_per_app.get(row.app_name, 0) + 1


		#Validate limits
		for app in users_per_app:
			allowed = allowed_users_per_app.get(app, 0)
			created = users_per_app.get(app, 0)
			if created > allowed:
				frappe.throw(
					f"You can only create {allowed} users for app '{app}'. "
					f"You tried to create {created} users."
				)

		# Auto link company field
		if self.company_name:
			self.company = self.company_name


		if self.is_master_user and self.billing_details:
			for row in self.billing_details:
				if not row.billing_package:
					if(frappe.db.exists("Billing Package", {"is_base_package": 1, "app": row.app_name})):
						base_package = frappe.db.get_value("Billing Package", {"is_base_package": 1, "app": row.app_name}, "name")
						row.billing_package = base_package
					else:
						frappe.throw(f"Please select a billing package for app {row.app_name} or create a base package for it.")

				if row.billing_package:
					pkg_role = frappe.db.get_value("Billing Package", row.billing_package, "billing_role")
					row.billing_role = pkg_role
					if not frappe.db.exists("Billing Package Ledger", {"user": self.email, "app_name": row.app_name, "billing_package": row.billing_package, "package_id": row.package_id}):
						row.package_id = generate_random_id()
		



	def on_update(self):
		old_doc = self.get_doc_before_save()

		package_changed_map = {}

		if old_doc:
			for old_row in old_doc.billing_details:
				for new_row in self.billing_details:
					if old_row.app_name == new_row.app_name:
						if old_row.billing_package != new_row.billing_package:
							package_changed_map[new_row.app_name] = True
		if not getattr(self.flags, "ignore_sync", False):
			self.sync_company()
			self.sync_users()
			self.delete_removed_child_users()


		if getattr(self.flags, "ignore_active_package_sync", False):
			return


		# Sync Active Package Details for child users
		for row in self.billing_user_detail:
			if package_changed_map.get(row.app_name):
				row.user_role = "User Role"
		for row in self.billing_user_detail:
			if not row.email:
				continue

			doc_name = frappe.db.get_value(
				"Billing Account Master",
				{"email": row.email}
			)

			if not doc_name:
				continue

			doc = frappe.get_doc("Billing Account Master", doc_name)
			if getattr(doc.flags, "from_child_creation", False):
				continue

			updated = False
			for detail in doc.billing_details:
				if detail.app_name == row.app_name:

					if package_changed_map.get(row.app_name):
						detail.billing_role = "User Role"

					else:
						detail.billing_role = row.user_role

					detail.package_id = generate_random_id()

					for val in self.billing_details:
						if val.app_name == row.app_name:
							detail.billing_package = val.billing_package
							updated = True

			if updated:
				doc.flags.ignore_sync = True
				doc.flags.ignore_active_package_sync = True
				doc.save(ignore_permissions=True)
				doc.sync_users()
		

		# create billing package ledger entry
		if self.is_master_user:
			for row in self.billing_details:

				pkg_doc = frappe.get_doc("Billing Package", row.billing_package)

				if pkg_doc.is_user_package:
					continue

				record_exists = frappe.db.exists(
					"Billing Package Ledger",
					{
						"user": self.email,
						"app_name": row.app_name,
						"package_id": row.package_id
					}
				)

				if not record_exists:
					package_doc = frappe.get_doc("Billing Package", row.billing_package)

					to_date = None
					total_tokens = 0

					if package_doc.package_type == "Day Based":
						days = package_doc.no_of_days or 0
						to_date = add_days(today(), days)

					elif package_doc.package_type == "Token Based":
						total_tokens = package_doc.total_token or 0
					doc = frappe.new_doc("Billing Package Ledger")
					doc.user = self.email
					doc.app_name = row.app_name
					doc.role = row.billing_role
					doc.billing_package = row.billing_package
					doc.billing_role = row.billing_role
					doc.package_id = row.package_id
					doc.status = "Active"
					doc.from_date = today()

					# existing
					doc.to_date = to_date  

					if package_doc.package_type == "Token Based":
						doc.total_tokens = total_tokens
						doc.remaining_tokens = total_tokens
						token_expiry_days = package_doc.token_expiry_days if package_doc.token_expiry_days != 0 else None
						doc.to_date = add_days(today(), token_expiry_days) if token_expiry_days else None

					doc.save(ignore_permissions=True)

					active_record_name = frappe.db.get_value(
						"Active Package Details",
						{
							"user": self.email,
							"app_name": row.app_name
						},
						"name"
					)

					if not active_record_name:
						record = frappe.new_doc("Active Package Details")
						record.user = self.email
						record.app_name = row.app_name
						record.billing_package = row.billing_package
						record.role = row.billing_role
						record.from_date = today()
						record.to_date = to_date
						record.status = "Active"
						record.package_id = row.package_id

						if package_doc.package_type == "Token Based":
							record.package_type = "Token Based"
							record.total_tokens = total_tokens
							record.remaining_tokens = total_tokens
							token_expiry_days = package_doc.token_expiry_days if package_doc.token_expiry_days != 0 else None
							record.to_date = add_days(today(), token_expiry_days) if token_expiry_days else None
						else:
							record.package_type = "Day Based"

						record.insert(ignore_permissions=True)

					else:

						active_record = frappe.get_doc("Active Package Details", active_record_name)

						ledger_record = frappe.get_doc("Billing Package Ledger", {"user": self.email, "app_name": row.app_name, "package_id": active_record.package_id})
						ledger_record.status = "Pending"
						ledger_record.days_left = date_diff(active_record.to_date, today())
						ledger_record.save(ignore_permissions=True)

						active_record.billing_package = row.billing_package
						active_record.role = row.billing_role
						active_record.from_date = today()
						active_record.to_date = to_date
						active_record.status = "Active"
						active_record.package_id = row.package_id

						if package_doc.package_type == "Token Based":
							active_record.package_type = "Token Based"
							active_record.total_tokens = total_tokens
							active_record.remaining_tokens = total_tokens
							active_record.to_date = add_days(today(), package_doc.token_expiry_days) if package_doc.token_expiry_days else None
						else:
							active_record.package_type = "Day Based"

						active_record.save(ignore_permissions=True)


		# Creating User Permissions

		# Company Permission	
		company_perm = frappe.db.get_value(
			"User Permission",
			{"user": self.email, "allow": "Company"},
			"name"
		)

		if not company_perm:
			doc = frappe.new_doc("User Permission")
			doc.user = self.email
			doc.allow = "Company"
			doc.for_value = self.company_name
			doc.insert(ignore_permissions=True)

		else:
			doc = frappe.get_doc("User Permission", company_perm)
			doc.for_value = self.company_name
			doc.save(ignore_permissions=True)


		# Billing Role Permissions (from child table)
		for row in self.billing_user_detail:
			if not row.user_role:
				continue

			role_perm = frappe.db.get_value(
				"User Permission",
				{
					"user": row.email,
					"allow": "Company",
					"for_value": self.company_name
				},
				"name"
			)

			if not role_perm:
				doc = frappe.new_doc("User Permission")
				doc.user = row.email
				doc.allow = "Company"
				doc.for_value = self.company_name
				doc.insert(ignore_permissions=True)
		self.sync_users()

	def sync_company(self):

		if not self.company_name:
			return

		company_data = {
			"company_name": self.company_name,
			"abbr": self.abbr,
			"default_currency": self.default_currency,
			"country": self.country,
			"is_group": self.is_group,
			"default_letter_head": self.default_letter_head,
			"gstin": self.gstin or None,
			"domain": self.domain,
			"date_of_establishment": self.date_of_establishment,
			"parent_company": self.parent_company
		}

		if frappe.db.exists("Company", self.company_name):

			frappe.db.set_value(
				"Company",
				self.company_name,
				company_data,
				update_modified=False
			)

		else:
			frappe.log_error(
				f"Company missing during sync: {self.company_name}",
				"sync_company error"
			)


  
	def get_billing_roles(self):
		roles = []

		for row in self.billing_details:
			if row.billing_role and row.billing_role not in roles:
				roles.append(row.billing_role)

		return roles


	def sync_users(self):
			master_password = self.user_password
			master_roles = []

			if self.is_master_user and self.billing_details:
				for row in self.billing_details:
					if row.billing_role and row.billing_role not in master_roles:
						master_roles.append(row.billing_role)
							
			elif not self.is_master_user and self.billing_details:
				for row in self.billing_details:
					if row.billing_role and row.billing_role not in master_roles:
						master_roles.append(row.billing_role)

			# Update the Master User in the system with ALL collected roles
			if self.email:
				self.create_or_update_user(
					email=self.email,
					first_name=self.first_name,
					middle_name=self.middle_name,
					last_name=self.last_name,
					password=master_password,
					language=self.language,
					time_zone=self.time_zone,
					roles=master_roles
				)

			
			child_users_data = {}
			
			for row in self.billing_user_detail:
				if not row.email:
					continue

				# If we haven't seen this email yet, set up a dictionary for them
				if row.email not in child_users_data:
					child_users_data[row.email] = {
						"first_name": row.first_name,
						"middle_name": row.middle_name,
						"last_name": row.last_name,
						"password": row.user_password,
						"roles": [],
						"apps": []
					}

				# Add the role to their list (avoiding duplicates)
				if row.user_role and row.user_role not in child_users_data[row.email]["roles"]:
					child_users_data[row.email]["roles"].append(row.user_role)

				# Find the matching master package for this specific app
				master_package_for_app = None
				if self.billing_details:
					for md in self.billing_details:
						if md.app_name == row.app_name:
							master_package_for_app = md.billing_package
							break

				# Save the app details to add to their personal Billing Account Master later
				child_users_data[row.email]["apps"].append({
					"app_name": row.app_name,
					"billing_role": row.user_role,
					"billing_package": master_package_for_app
				})


			for child_email, child_data in child_users_data.items():
				
				self.create_or_update_user(
					email=child_email,
					first_name=child_data["first_name"],
					middle_name=child_data["middle_name"],
					last_name=child_data["last_name"],
					password=child_data["password"],
					language=self.language,
					time_zone=self.time_zone,
					roles=child_data["roles"] # Passes multiple roles at once!
				)

				existing_doc_name = frappe.db.exists(
					"Billing Account Master",
					{
						"email": child_email,
						"is_master_user": 0
					}
				)

				if not existing_doc_name:
					try:
						base_doc = frappe.get_doc({
							"doctype": "Billing Account Master",
							"company_name": self.company_name,
							"abbr": self.abbr,
							"default_currency": self.default_currency,
							"country": self.country,
							"email": child_email,
							"first_name": child_data["first_name"],
							"middle_name": child_data["middle_name"],
							"last_name": child_data["last_name"],
							"language": self.language,
							"time_zone": self.time_zone,
							"is_master_user": 0,
							"company_exist": 1
						})

						# Append all apps assigned to them
						for app_info in child_data["apps"]:
							if app_info["billing_package"]: 
								base_doc.append("billing_details", {
									"app_name": app_info["app_name"],
									"billing_package": app_info["billing_package"],
									"billing_role": app_info["billing_role"]
								})

						base_doc.flags.from_child_creation = True
						base_doc.flags.ignore_sync = True
						base_doc.insert(ignore_permissions=True)
						base_doc.flags.ignore_sync = False

					except Exception:
						frappe.log_error(
							frappe.get_traceback(),
							f"Child Billing Account Creation Failed for {child_email}"
						)

				else:
					try:
						base_doc = frappe.get_doc("Billing Account Master", existing_doc_name)
						doc_changed = False
						
						existing_apps = [d.app_name for d in base_doc.billing_details]

						for app_info in child_data["apps"]:
							if app_info["app_name"] not in existing_apps:
								if app_info["billing_package"]:
									base_doc.append("billing_details", {
										"app_name": app_info["app_name"],
										"billing_package": app_info["billing_package"],
										"billing_role": app_info["billing_role"]
									})
									doc_changed = True
							else:
								for d in base_doc.billing_details:
									if d.app_name == app_info["app_name"]:
										if d.billing_role != app_info["billing_role"] or d.billing_package != app_info["billing_package"]:
											d.billing_role = app_info["billing_role"]
											d.billing_package = app_info["billing_package"]
											doc_changed = True

						if doc_changed:
							base_doc.flags.from_child_creation = True
							base_doc.flags.ignore_sync = True
							base_doc.save(ignore_permissions=True)
							base_doc.flags.ignore_sync = False

					except Exception:
						frappe.log_error(
							frappe.get_traceback(),
							f"Child Billing Account Update Failed for {child_email}"
						)

			self.user_password = None
			for row in self.billing_user_detail:
				row.user_password = None



	def create_or_update_user(self, email, first_name, middle_name, last_name, password, language, time_zone, roles=None):

		system_timezone = frappe.db.get_single_value(
			"System Settings",
			"time_zone"
		) or "Asia/Kolkata"

		final_timezone = time_zone or system_timezone

		username_value = email.split("@")[0]

		full_name_value = " ".join(
			filter(None, [first_name, middle_name, last_name])
		)

		user_data = {
			"first_name": first_name,
			"middle_name": middle_name,
			"last_name": last_name,
			"full_name": full_name_value,
			"username": username_value,
			"time_zone": final_timezone,
			"language": language,
			"enabled": 1   
		}

		if frappe.db.exists("User", email):

			user = frappe.get_doc("User", email)

			if user.enabled == 0:
				user.enabled = 1

			for k, v in user_data.items():
				setattr(user, k, v)

			user.roles = []

			user.append("roles", {"role": "All"})
			user.append("roles", {"role": "Desk User"})

			if roles:
				for role in roles:
					if frappe.db.exists("Role", role):
						user.append("roles", {"role": role})

			user.save(ignore_permissions=True)

			if password:
				update_password(email, password)

		else:

			roles_list = [
				{"role": "All"},
				{"role": "Desk User"}
			]

			if roles:
				for role in roles:
					if frappe.db.exists("Role", role):
						roles_list.append({"role": role})

			doc = frappe.get_doc({
				"doctype": "User",
				"email": email,
				"user_type": "System User",
				"send_welcome_email": 0,
				"roles": roles_list,
				"enabled": 1, 
				**user_data
			})

			doc.insert(ignore_permissions=True)

			if password:
				update_password(email, password)



	def delete_removed_child_users(self):

		if not self.is_master_user:
			return

		if self.flags.in_insert:
			return

		if getattr(self.flags, "from_child_creation", False):
			return

		if not self.company_name:
			return

		current_child_emails = [
			row.email for row in self.billing_user_detail if row.email
		]

		base_users = frappe.get_all(
			"Billing Account Master",
			filters={
				"company_name": self.company_name,
				"is_master_user": 0
			},
			fields=["name", "email"]
		)

		for base in base_users:

			if base.email not in current_child_emails:

				if base.email and frappe.db.exists("User", base.email):
					frappe.db.set_value("User", base.email, "enabled", 0)

				frappe.delete_doc(
					"Billing Account Master",
					base.name,
					ignore_permissions=True,
					force=True
				)


	def on_trash(self):
		company_perms = frappe.get_all(
			"User Permission",
			filters={"user": self.email, "allow": "Company"},
			pluck="name"
		)
		for perm in company_perms:
			frappe.delete_doc("User Permission", perm, ignore_permissions=True)

		billing_perms = frappe.get_all(
			"User Permission",
			filters={"user": self.email, "allow": "Billing Role"},
			pluck="name"
		)
		for perm in billing_perms:
			frappe.delete_doc("User Permission", perm, ignore_permissions=True)


		if self.is_master_user:
			
			base_users = frappe.get_all(
				"Billing Account Master",
				filters={
					"company_name": self.company_name,
					"is_master_user": 0
				},
				fields=["name", "email"]
			)

			emails_to_clear = [self.email] if self.email else []

			for base in base_users:
				if base.email:
					emails_to_clear.append(base.email)

				# Delete User
				if base.email and frappe.db.exists("User", base.email):
					frappe.delete_doc("User", base.email, ignore_permissions=True, force=True)

				# Delete Billing Account Master child record
				frappe.delete_doc("Billing Account Master", base.name, ignore_permissions=True, force=True)


			# Delete Active Package Details
			if emails_to_clear:
				active_packages = frappe.get_all(
					"Active Package Details",
					filters={"user": ["in", emails_to_clear]},
					pluck="name"
				)
				for pkg in active_packages:
					frappe.delete_doc("Active Package Details", pkg, ignore_permissions=True, force=True)


			# 🔹 DELETE BILLING PACKAGE LEDGER
			if emails_to_clear:
				ledgers = frappe.get_all(
					"Billing Package Ledger",
					filters={"user": ["in", emails_to_clear]},
					pluck="name"
				)
				for ledger in ledgers:
					frappe.delete_doc("Billing Package Ledger", ledger, ignore_permissions=True, force=True)


			# Delete Master User
			if self.email and frappe.db.exists("User", self.email):
				frappe.delete_doc("User", self.email, ignore_permissions=True, force=True)
			
			#delete address
			links = []
			if self.company_name:
				links.append(("Company", self.company_name))

			if self.name:
				links.append(("Billing Account Master", self.name))

			address_names = set()

			for link_doctype, link_name in links:
				linked_addresses = frappe.get_all(
					"Dynamic Link",
					filters={
						"link_doctype": link_doctype,
						"link_name": link_name,
						"parenttype": "Address"
					},
					pluck="parent"
				)
				address_names.update(linked_addresses)

			# Delete addresses
			for addr in address_names:
				if frappe.db.exists("Address", addr):
					frappe.delete_doc("Address", addr, ignore_permissions=True, force=True)

			# Delete Company
			if self.company_name and frappe.db.exists("Company", self.company_name):
				frappe.delete_doc("Company", self.company_name, ignore_permissions=True, force=True)


		# Base User Deletion
		else:
			master_name = frappe.db.get_value(
				"Billing Account Master",
				{
					"company_name": self.company_name,
					"is_master_user": 1
				},
				"name"
			)

			# Remove base user from Master doc's child table
			if master_name:
				master_doc = frappe.get_doc("Billing Account Master", master_name)
				master_doc.flags.ignore_sync = True

				master_doc.billing_user_detail = [
					row for row in master_doc.billing_user_detail
					if row.email != self.email
				]
				master_doc.save(ignore_permissions=True)


			# Delete Active Package Details
			if self.email:
				active_packages = frappe.get_all(
					"Active Package Details",
					filters={"user": self.email},
					pluck="name"
				)
				for pkg in active_packages:
					frappe.delete_doc("Active Package Details", pkg, ignore_permissions=True, force=True)


			if self.email:
				ledgers = frappe.get_all(
					"Billing Package Ledger",
					filters={"user": self.email},
					pluck="name"
				)
				for ledger in ledgers:
					frappe.delete_doc("Billing Package Ledger", ledger, ignore_permissions=True, force=True)


			# Delete User ONLY if master does NOT exist
			if self.email and frappe.db.exists("User", self.email):

				if not master_name:
					frappe.delete_doc("User", self.email, ignore_permissions=True, force=True)


@frappe.whitelist(allow_guest=True)
def create_billing_registration():
    data = frappe.local.form_dict.get("data")

    if not data:
        frappe.throw("No data received in request")

    if isinstance(data, str):
        data = frappe.parse_json(data)
        
    company_name = data.get("company_name")

    original_user = frappe.session.user
    frappe.set_user("Administrator")

    try:
        if frappe.db.exists("Company", company_name):
            company = frappe.get_doc("Company", company_name)
        else:
            company = frappe.new_doc("Company")
            company.company_name = company_name
            company.abbr = data.get("abbr")
            company.default_currency = data.get("default_currency")
            company.country = data.get("country")
            
            # Map GSTIN
            if data.get("gstin"):
                company.gstin = data.get("gstin") 
                
            company.insert(ignore_permissions=True)

        #Create Billing Account Master
        doc = frappe.new_doc("Billing Account Master")
        doc.update({
            "company_name": data.get("company_name"),
            "abbr": data.get("abbr"),
            "default_currency": data.get("default_currency"),
            "country": data.get("country"),
            "gstin": data.get("gstin"),  
            "email": data.get("email"),
            "user_password": data.get("user_password"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "is_master_user": 1
        })

        # Append child table rows
        for app in data.get("billing_details", []):
            doc.append("billing_details", {
                "app_name": app.get("title")
            })

        doc.insert(ignore_permissions=True)

        if data.get("address_line1") and data.get("city"):
            address = frappe.new_doc("Address")
            address.update({
                "address_title": data.get("company_name"),
                "address_line1": data.get("address_line1"),
                "address_line2": data.get("address_line2"),
                "city": data.get("city"),
                "state": data.get("state"),
                "pincode": data.get("pincode"),
                "country": data.get("country")
            })

            address.append("links", {
                "link_doctype": "Company",
                "link_name": company.name,
                "link_title": company.company_name
            })

            address.append("links", {
                "link_doctype": "Billing Account Master",
                "link_name": doc.name,
                "link_title": doc.company_name                 
            })

            address.insert(ignore_permissions=True)
        else:
            frappe.logger().warning(
                f"Address skipped for {data.get('company_name')} due to missing address_line1 or city"
            )

        frappe.db.commit()
        return {"status": "success"}

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Billing Registration Error")
        return {"status": "error", "message": str(e)}

    finally:
        frappe.set_user(original_user)


@frappe.whitelist(allow_guest=True)
def get_registration_options():
    currencies = frappe.get_all("Currency", pluck="name", ignore_permissions=True)
    countries = frappe.get_all("Country", pluck="name", ignore_permissions=True)

    configured_apps = frappe.get_all(
        "Billing Module Configuration", 
        pluck="app", 
        ignore_permissions=True
    )

    ignore_apps = ["frappe", "erpnext"]
    apps = []

    for a in configured_apps:
        if a and a not in ignore_apps and a not in apps:
            apps.append(a)

    return {
        "currencies": currencies,
        "countries": countries,
        "apps": apps
    }


#api for custom block for package info on dashboard 
@frappe.whitelist(allow_guest=True)
def get_user_package():

    user = frappe.session.user

    data = frappe.get_all(
        "Billing Package Ledger",
        filters={
            "user": user,
            "status": "Active"
        },
        fields=[
            "app_name",
            "billing_package",
            "role",
            "from_date",
            "to_date",
            "package_id"
        ],
        ignore_permissions=True 
    )

    for entry in data:

        # Days remaining
        if entry.to_date:
            entry['days_remaining'] = date_diff(entry.to_date, today())
        else:
            entry['days_remaining'] = 0

        package_type = frappe.db.get_value(
            "Billing Package",
            entry.billing_package,
            "package_type"
        )

        entry["package_type"] = package_type

        remaining = frappe.db.get_value(
            "Active Package Details",
            {
                "user": user,
                "app_name": entry.app_name,
                "package_id": entry.package_id
            },
            "remaining_tokens"
        )

        entry["remaining_tokens"] = remaining if remaining else 0

    return data