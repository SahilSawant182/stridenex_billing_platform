# Copyright (c) 2026, Quantbit Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.password import update_password
from frappe.utils import today, add_days, date_diff
from quantbit_billing_platform.utils import generate_random_id


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
					base_package = frappe.db.get_value(
						"Billing Package", 
						{
							"is_base_package": 1, 
							"app_name": row.app_name,
							"billing_role": getattr(row, "billing_role", None)
						}, 
						"name"
					)
					if base_package:
						row.billing_package = base_package
					else:
						frappe.throw(f"Please select a billing package for app {row.app_name} or create a base package for this role.")

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


		# # Creating User Permissions

		# # Company Permission	
		# company_perm = frappe.db.get_value(
		# 	"User Permission",
		# 	{"user": self.email, "allow": "Company"},
		# 	"name"
		# )

		# if not company_perm:
		# 	doc = frappe.new_doc("User Permission")
		# 	doc.user = self.email
		# 	doc.allow = "Company"
		# 	doc.for_value = self.company_name
		# 	doc.insert(ignore_permissions=True)

		# else:
		# 	doc = frappe.get_doc("User Permission", company_perm)
		# 	doc.for_value = self.company_name
		# 	doc.save(ignore_permissions=True)


		# # Billing Role Permissions (from child table)
		# for row in self.billing_user_detail:
		# 	if not row.user_role:
		# 		continue

		# 	role_perm = frappe.db.get_value(
		# 		"User Permission",
		# 		{
		# 			"user": row.email,
		# 			"allow": "Company",
		# 			"for_value": self.company_name
		# 		},
		# 		"name"
		# 	)

		# 	if not role_perm:
		# 		doc = frappe.new_doc("User Permission")
		# 		doc.user = row.email
		# 		doc.allow = "Company"
		# 		doc.for_value = self.company_name
		# 		doc.insert(ignore_permissions=True)
		self.sync_users()

	def sync_company(self):
		return


  
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


	# FIX: Outdented to class level
def on_trash(self):
        if self.is_master_user:
            emails_to_clear = [self.email] if self.email else []
            if getattr(self, "account_type", "Organization") == "Organization" and self.company_name:
                base_users = frappe.get_all("Billing Account Master", filters={"company_name": self.company_name, "is_master_user": 0}, fields=["name", "email"])
                for base in base_users:
                    if base.email:
                        emails_to_clear.append(base.email)
                    if base.email and frappe.db.exists("User", base.email):
                        frappe.delete_doc("User", base.email, ignore_permissions=True, force=True)
                    frappe.delete_doc("Billing Account Master", base.name, ignore_permissions=True, force=True)

            if emails_to_clear:
                active_packages = frappe.get_all("Active Package Details", filters={"user": ["in", emails_to_clear]}, pluck="name")
                for pkg in active_packages:
                    frappe.delete_doc("Active Package Details", pkg, ignore_permissions=True, force=True)

                ledgers = frappe.get_all("Billing Package Ledger", filters={"user": ["in", emails_to_clear]}, pluck="name")
                for ledger in ledgers:
                    frappe.delete_doc("Billing Package Ledger", ledger, ignore_permissions=True, force=True)

            if self.email and frappe.db.exists("User", self.email):
                frappe.delete_doc("User", self.email, ignore_permissions=True, force=True)
        else:
            if getattr(self, "account_type", "Organization") == "Organization" and self.company_name:
                master_name = frappe.db.get_value("Billing Account Master", {"company_name": self.company_name, "is_master_user": 1}, "name")
                if master_name:
                    master_doc = frappe.get_doc("Billing Account Master", master_name)
                    master_doc.flags.ignore_sync = True
                    master_doc.billing_user_detail = [row for row in master_doc.billing_user_detail if row.email != self.email]
                    master_doc.save(ignore_permissions=True)

            if self.email:
                active_packages = frappe.get_all("Active Package Details", filters={"user": self.email}, pluck="name")
                for pkg in active_packages:
                    frappe.delete_doc("Active Package Details", pkg, ignore_permissions=True, force=True)
                
                ledgers = frappe.get_all("Billing Package Ledger", filters={"user": self.email}, pluck="name")
                for ledger in ledgers:
                    frappe.delete_doc("Billing Package Ledger", ledger, ignore_permissions=True, force=True)

            if self.email and frappe.db.exists("User", self.email):
                is_org = getattr(self, "account_type", "Organization") == "Organization"
                master_exists = is_org and getattr(self, "company_name", None) and frappe.db.exists("Billing Account Master", {"company_name": self.company_name, "is_master_user": 1})
                if not master_exists:
                    frappe.delete_doc("User", self.email, ignore_permissions=True, force=True)










@frappe.whitelist(allow_guest=True)
def create_billing_registration():
    data = frappe.local.form_dict.get("data")
    if not data:
        frappe.throw("No data received in request")

    if isinstance(data, str):
        data = frappe.parse_json(data)
        
    account_type = data.get("account_type", "Organization")
    role_type = data.get("role_type")
    
    # Individuals won't have a company name, so default to None
    company_name = data.get("company_name") if account_type == "Organization" else None

    original_user = frappe.session.user
    frappe.set_user("Administrator")

    try:
        doc = frappe.new_doc("Billing Account Master")
        doc.update({
            "account_type": account_type,
            "company_name": company_name,
            "abbr": data.get("abbr") if account_type == "Organization" else None,
            "default_currency": data.get("default_currency"),
            "country": data.get("country"),
            
            # Allow GSTIN only for Organizations, default None for Individuals
            "gstin": data.get("gstin") if account_type == "Organization" else None,
            
            "email": data.get("email"),
            "user_password": data.get("user_password"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            
            # These must match exactly with 'address_line1' in the Doctype
            "address_line1": data.get("address_line1"),
            "address_line2": data.get("address_line2"),
            "city": data.get("city"),	
            "state": data.get("state"),
            "pincode": data.get("pincode"),
            
            "is_master_user": 1
        })

        # Dynamic Base Package Assignment
        for app in data.get("billing_details", []):
            app_name = app.get("title")
            base_package = frappe.db.get_value(
                "Billing Package", 
                {"is_base_package": 1, "app_name": app_name, "billing_role": role_type}, 
                "name"
            )
            
            if not base_package:
                frappe.throw(f"No base package configured for app '{app_name}' and role '{role_type}'")

            doc.append("billing_details", {
                "app_name": app_name, 
                "billing_package": base_package, 
                "billing_role": role_type
            })

        doc.insert(ignore_permissions=True)
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