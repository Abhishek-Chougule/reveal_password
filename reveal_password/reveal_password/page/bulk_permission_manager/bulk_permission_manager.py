# Copyright (c) 2025, Abhishek Chougule and contributors
# For license information, please see license.txt

import frappe
from frappe import _


@frappe.whitelist()
def get_doctypes_with_password_fields():
	"""Get all DocTypes that have password fields."""
	doctypes = frappe.get_all("DocType", filters={"istable": 0}, pluck="name")
	
	doctypes_with_password = []
	for doctype in doctypes:
		try:
			meta = frappe.get_meta(doctype)
			has_password = any(field.fieldtype == "Password" for field in meta.fields)
			if has_password:
				doctypes_with_password.append(doctype)
		except Exception:
			continue
	
	return sorted(doctypes_with_password)


@frappe.whitelist()
def get_permission_matrix(doctype=None, role=None):
	"""
	Get the permission matrix for bulk editing.
	
	Args:
		doctype: Optional DocType filter
		role: Optional Role filter
		
	Returns:
		List of permission entries
	"""
	# Get all password fields from relevant DocTypes
	doctypes = [doctype] if doctype else get_doctypes_with_password_fields()
	
	# Get all roles or filtered role
	if role:
		roles = [role]
	else:
		roles = frappe.get_all("Role", filters={"disabled": 0}, pluck="name", order_by="name")
	
	matrix = []
	
	for dt in doctypes:
		try:
			meta = frappe.get_meta(dt)
			password_fields = [f.fieldname for f in meta.fields if f.fieldtype == "Password"]
			
			for field in password_fields:
				for r in roles:
					# Check if permission exists
					existing = frappe.db.get_value(
						"Field Permission Matrix",
						{
							"doctype_name": dt,
							"field_name": field,
							"role": r
						},
						"can_reveal"
					)
					
					matrix.append({
						"doctype": dt,
						"field": field,
						"role": r,
						"can_reveal": existing if existing is not None else 0
					})
		except Exception:
			continue
	
	return matrix


@frappe.whitelist()
def save_bulk_permissions(permissions):
	"""
	Save bulk permission updates.
	
	Args:
		permissions: List of permission dictionaries
	"""
	if isinstance(permissions, str):
		import json
		permissions = json.loads(permissions)
	
	updated = 0
	created = 0
	
	for perm in permissions:
		try:
			# Check if entry exists
			existing = frappe.db.get_value(
				"Field Permission Matrix",
				{
					"doctype_name": perm["doctype"],
					"field_name": perm["field"],
					"role": perm["role"]
				},
				"name"
			)
			
			if existing:
				# Update existing
				doc = frappe.get_doc("Field Permission Matrix", existing)
				doc.can_reveal = perm["can_reveal"]
				doc.save(ignore_permissions=True)
				updated += 1
			else:
				# Create new
				doc = frappe.get_doc({
					"doctype": "Field Permission Matrix",
					"doctype_name": perm["doctype"],
					"field_name": perm["field"],
					"role": perm["role"],
					"can_reveal": perm["can_reveal"]
				})
				doc.insert(ignore_permissions=True)
				created += 1
		except Exception as e:
			frappe.log_error(f"Error saving permission: {str(e)}")
			continue
	
	frappe.db.commit()
	
	return {
		"updated": updated,
		"created": created,
		"total": updated + created
	}
