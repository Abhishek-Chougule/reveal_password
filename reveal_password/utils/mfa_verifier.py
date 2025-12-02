# Copyright (c) 2025, Abhishek Chougule and contributors
# For license information, please see license.txt

"""
MFA verification utilities for password reveal.

This module provides MFA verification functions that integrate
with the reveal_password flow.
"""

import frappe
from frappe import _
import logging

logger = logging.getLogger(__name__)


@frappe.whitelist()
def verify_mfa_for_reveal(token: str, user: str = None) -> dict:
	"""
	Verify MFA token for password reveal operation.
	
	Args:
		token: The MFA token or backup code to verify
		user: User to verify for (defaults to current user)
		
	Returns:
		Dictionary with verification status and message
	"""
	if not user:
		user = frappe.session.user
	
	try:
		# Check if MFA is globally enabled
		settings = frappe.get_single("Password Reveal Settings")
		if not settings.enable_mfa:
			return {"verified": True, "message": "MFA not required"}
		
		# Check if user has MFA enabled
		mfa_secret = frappe.db.get_value("MFA Secret", {"user": user}, "name")
		if not mfa_secret:
			return {"verified": True, "message": "MFA not configured for user"}
		
		mfa_doc = frappe.get_doc("MFA Secret", mfa_secret)
		
		if not mfa_doc.is_enabled:
			return {"verified": True, "message": "MFA not enabled for user"}
		
		# Try TOTP verification
		if mfa_doc.verify_token(token):
			return {"verified": True, "message": "TOTP verified"}
		
		# Try backup code verification
		from reveal_password.reveal_password.doctype.mfa_secret.mfa_secret import verify_backup_code
		if verify_backup_code(token):
			return {"verified": True, "message": "Backup code verified"}
		
		return {"verified": False, "message": "Invalid token or backup code"}
		
	except Exception as e:
		logger.error(f"Error verifying MFA token: {str(e)}")
		return {"verified": False, "message": f"Verification error: {str(e)}"}


@frappe.whitelist()
def check_mfa_required(user: str = None) -> dict:
	"""
	Check if MFA is required for a user.
	
	Args:
		user: User to check (defaults to current user)
		
	Returns:
		Dictionary with MFA requirement status
	"""
	if not user:
		user = frappe.session.user
	
	try:
		# Check global setting
		settings = frappe.get_single("Password Reveal Settings")
		if not settings.enable_mfa:
			return {"required": False, "reason": "MFA disabled globally"}
		
		# Check user MFA status
		mfa_secret = frappe.db.get_value("MFA Secret", {"user": user}, ["name", "is_enabled"], as_dict=True)
		
		if not mfa_secret:
			return {"required": False, "reason": "MFA not configured", "setup_url": "/app/mfa-setup"}
		
		if not mfa_secret.is_enabled:
			return {"required": False, "reason": "MFA not enabled", "setup_url": "/app/mfa-setup"}
		
		return {"required": True, "reason": "MFA enabled and required"}
		
	except Exception as e:
		logger.error(f"Error checking MFA requirement: {str(e)}")
		return {"required": False, "reason": f"Error: {str(e)}"}
