# Copyright (c) 2025, Abhishek Chougule and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class FieldPermissionMatrix(Document):
	def validate(self):
		"""Validate the permission matrix entry."""
		# Check if the DocType exists
		if not frappe.db.exists("DocType", self.doctype_name):
			frappe.throw(f"DocType '{self.doctype_name}' does not exist")
		
		# Check if the field exists in the DocType
		if not self.field_exists():
			frappe.throw(f"Field '{self.field_name}' does not exist in DocType '{self.doctype_name}'")
		
		# Check for duplicate entries
		self.check_duplicate()
	
	def field_exists(self):
		"""Check if the field exists in the specified DocType."""
		meta = frappe.get_meta(self.doctype_name)
		return meta.has_field(self.field_name)
	
	def check_duplicate(self):
		"""Check for duplicate permission entries."""
		existing = frappe.db.exists("Field Permission Matrix", {
			"doctype_name": self.doctype_name,
			"field_name": self.field_name,
			"role": self.role,
			"name": ["!=", self.name]
		})
		
		if existing:
			frappe.throw(f"Permission entry already exists for {self.role} on {self.doctype_name}.{self.field_name}")


@frappe.whitelist()
def get_password_fields(doctype):
	"""
	Get all password fields from a DocType.
	
	Args:
		doctype: DocType name
		
	Returns:
		List of password field names
	"""
	if not frappe.db.exists("DocType", doctype):
		return []
	
	meta = frappe.get_meta(doctype)
	password_fields = []
	
	for field in meta.fields:
		if field.fieldtype == "Password":
			password_fields.append(field.fieldname)
	
	return password_fields


@frappe.whitelist()
def get_permission_summary(doctype=None, role=None):
	"""
	Get a summary of field permissions.
	
	Args:
		doctype: Optional DocType filter
		role: Optional Role filter
		
	Returns:
		List of permission summaries
	"""
	filters = {}
	if doctype:
		filters["doctype_name"] = doctype
	if role:
		filters["role"] = role
	
	permissions = frappe.get_all(
		"Field Permission Matrix",
		filters=filters,
		fields=["doctype_name", "field_name", "role", "can_reveal"],
		order_by="doctype_name, field_name"
	)
	
	return permissions
