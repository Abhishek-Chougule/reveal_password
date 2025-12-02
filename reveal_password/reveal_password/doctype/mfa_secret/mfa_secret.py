# Copyright (c) 2025, Abhishek Chougule and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now
import io
import base64


class MFASecret(Document):
	def before_insert(self):
		"""Generate TOTP secret and QR code before inserting."""
		if not self.secret_key:
			# Generate a random secret key
			import pyotp
			self.secret_key = pyotp.random_base32()
		
		if not self.setup_date:
			self.setup_date = now()
		
		# Generate QR code
		self.generate_qr_code()
	
	def generate_qr_code(self):
		"""Generate QR code for TOTP setup."""
		if not self.secret_key:
			return

		import pyotp
		import qrcode

		# Create TOTP URI
		totp = pyotp.TOTP(self.secret_key)
		uri = totp.provisioning_uri(
			name=self.user,
			issuer_name="Reveal Password"
		)
		
		# Generate QR code
		qr = qrcode.QRCode(version=1, box_size=10, border=5)
		qr.add_data(uri)
		qr.make(fit=True)
		
		# Create image
		img = qr.make_image(fill_color="black", back_color="white")
		
		# Convert to base64
		buffer = io.BytesIO()
		img.save(buffer, format='PNG')
		img_str = base64.b64encode(buffer.getvalue()).decode()
		
		# Save as data URI
		self.qr_code = f"data:image/png;base64,{img_str}"
	
	def verify_token(self, token):
		"""
		Verify a TOTP token.
		
		Args:
			token: 6-digit TOTP token
			
		Returns:
			True if valid, False otherwise
		"""
		if not self.is_enabled:
			return False
		
		import pyotp
		totp = pyotp.TOTP(self.secret_key)
		is_valid = totp.verify(token, valid_window=1)  # Allow 30 seconds window
		
		if is_valid:
			self.last_verified = now()
			self.save(ignore_permissions=True)
		
		return is_valid


@frappe.whitelist()
def setup_mfa():
	"""
	Setup MFA for the current user.
	
	Returns:
		Dictionary with secret and QR code
	"""
	user = frappe.session.user
	
	# Check if MFA already exists
	existing = frappe.db.exists("MFA Secret", {"user": user})
	
	if existing:
		doc = frappe.get_doc("MFA Secret", existing)
		# Regenerate QR code
		doc.generate_qr_code()
		doc.save(ignore_permissions=True)
	else:
		# Create new MFA secret
		doc = frappe.get_doc({
			"doctype": "MFA Secret",
			"user": user,
			"is_enabled": 0
		})
		doc.insert(ignore_permissions=True)
	
	return {
		"secret": doc.secret_key,
		"qr_code": doc.qr_code,
		"user": user
	}


@frappe.whitelist()
def enable_mfa(token):
	"""
	Enable MFA after verifying the initial token.
	
	Args:
		token: 6-digit TOTP token
		
	Returns:
		Success status and backup codes
	"""
	user = frappe.session.user
	
	mfa_secret = frappe.get_doc("MFA Secret", {"user": user})
	
	# Verify token
	if not mfa_secret.verify_token(token):
		frappe.throw("Invalid token. Please try again.")
	
	# Enable MFA
	mfa_secret.is_enabled = 1
	mfa_secret.save(ignore_permissions=True)
	
	# Generate backup codes
	backup_codes = generate_backup_codes(user)
	
	return {
		"success": True,
		"backup_codes": backup_codes
	}


@frappe.whitelist()
def disable_mfa():
	"""Disable MFA for the current user."""
	user = frappe.session.user
	
	mfa_secret = frappe.db.get_value("MFA Secret", {"user": user}, "name")
	
	if mfa_secret:
		doc = frappe.get_doc("MFA Secret", mfa_secret)
		doc.is_enabled = 0
		doc.save(ignore_permissions=True)
		
		# Delete unused backup codes
		frappe.db.delete("MFA Backup Code", {"user": user, "is_used": 0})
		frappe.db.commit()
		
		return {"success": True}
	
	return {"success": False, "message": "MFA not configured"}


def generate_backup_codes(user, count=10):
	"""
	Generate backup codes for emergency access.
	
	Args:
		user: User identifier
		count: Number of backup codes to generate
		
	Returns:
		List of backup codes
	"""
	import secrets
	
	# Delete old unused backup codes
	frappe.db.delete("MFA Backup Code", {"user": user, "is_used": 0})
	
	backup_codes = []
	
	for _ in range(count):
		# Generate 8-character alphanumeric code
		code = secrets.token_hex(4).upper()
		
		doc = frappe.get_doc({
			"doctype": "MFA Backup Code",
			"user": user,
			"code": code,
			"is_used": 0,
			"created_date": now()
		})
		doc.insert(ignore_permissions=True)
		
		backup_codes.append(code)
	
	frappe.db.commit()
	
	return backup_codes


@frappe.whitelist()
def verify_backup_code(code):
	"""
	Verify and use a backup code.
	
	Args:
		code: Backup code
		
	Returns:
		True if valid, False otherwise
	"""
	user = frappe.session.user
	
	backup_code = frappe.db.get_value(
		"MFA Backup Code",
		{"user": user, "code": code, "is_used": 0},
		"name"
	)
	
	if backup_code:
		doc = frappe.get_doc("MFA Backup Code", backup_code)
		doc.is_used = 1
		doc.used_date = now()
		doc.save(ignore_permissions=True)
		frappe.db.commit()
		
		return True
	
	return False
