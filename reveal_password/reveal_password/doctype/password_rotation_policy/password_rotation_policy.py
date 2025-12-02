# Copyright (c) 2025, Abhishek Chougule and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, now_datetime, get_datetime
import secrets
import string
import json

class PasswordRotationPolicy(Document):
	def validate(self):
		self.calculate_next_rotation()
		self.validate_target_field()

	def validate_target_field(self):
		if self.target_doctype and self.target_field:
			meta = frappe.get_meta(self.target_doctype)
			has_field = False
			for field in meta.fields:
				if field.fieldname == self.target_field:
					has_field = True
					if field.fieldtype != "Password":
						frappe.throw(f"Field {self.target_field} in {self.target_doctype} is not a Password field")
					break
			if not has_field:
				frappe.throw(f"Field {self.target_field} not found in {self.target_doctype}")

	def calculate_next_rotation(self):
		if not self.enabled:
			self.next_rotation = None
			return

		days = 30
		if self.frequency == "Daily":
			days = 1
		elif self.frequency == "Weekly":
			days = 7
		elif self.frequency == "Custom":
			days = self.rotation_interval_days or 30
		
		# If last rotation exists, calculate from there, otherwise from now
		base_date = get_datetime(self.last_rotation) if self.last_rotation else now_datetime()
		
		# If next rotation is already set and in future, keep it (unless frequency changed logic is needed, but simple for now)
		# Actually, let's always recalculate based on last_rotation to be safe
		self.next_rotation = add_days(base_date, days)

	def generate_password(self):
		length = self.password_length or 16
		chars = string.ascii_letters
		if self.use_numbers:
			chars += string.digits
		if self.use_special_chars:
			chars += "!@#$%^&*()_+-=[]{}|;:,.<>?"
		
		return ''.join(secrets.choice(chars) for _ in range(length))

	def execute_rotation(self):
		"""
		Execute the password rotation for matching documents.
		"""
		if not self.enabled:
			return

		filters = {}
		if self.filter_condition:
			try:
				filters = json.loads(self.filter_condition)
			except Exception:
				frappe.log_error(f"Invalid filter condition in policy {self.name}")
				return

		# Fetch documents to rotate
		docs = frappe.get_all(self.target_doctype, filters=filters, pluck='name')
		
		success_count = 0
		failure_count = 0

		for doc_name in docs:
			try:
				new_password = self.generate_password()
				
				# Update document
				doc = frappe.get_doc(self.target_doctype, doc_name)
				
				# Store old password (encrypted) for history - optional, requires getting decrypted first
				# For security, we might not want to store the old password unless strictly necessary.
				# Let's just update it.
				
				doc.set(self.target_field, new_password)
				doc.save(ignore_permissions=True)
				
				# Log history
				self.log_history(doc_name, "Success")
				success_count += 1
				
			except Exception as e:
				failure_count += 1
				self.log_history(doc_name, "Failure", str(e))
				frappe.log_error(f"Failed to rotate password for {doc_name}: {str(e)}")

		# Update policy state
		self.last_rotation = now_datetime()
		self.calculate_next_rotation()
		self.save(ignore_permissions=True)
		
		return success_count, failure_count

	def log_history(self, doc_name, status, error=None):
		history = frappe.get_doc({
			"doctype": "Password Rotation History",
			"policy": self.name,
			"target_doctype": self.target_doctype,
			"target_docname": doc_name,
			"rotation_date": now_datetime(),
			"status": status,
			"error_message": error
		})
		history.insert(ignore_permissions=True)

@frappe.whitelist()
def run_rotation(policy_name):
	policy = frappe.get_doc("Password Rotation Policy", policy_name)
	success, fail = policy.execute_rotation()
	return {"success": success, "failed": fail}
