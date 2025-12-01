# Copyright (c) 2025, Abhishek Chougule and contributors
# For license information, please see license.txt

"""
Enhanced password reveal functionality with comprehensive security checks.

This module provides the core password reveal functionality with:
- Input validation
- Rate limiting
- Audit logging
- Permission checks
- Error handling
"""

import frappe
from frappe import _
from frappe.utils.password import get_decrypted_password
from frappe.exceptions import PermissionError, ValidationError
import logging
from typing import Optional

# Import utilities
from reveal_password.utils.rate_limiter import rate_limit
from reveal_password.utils.audit_logger import log_password_reveal

logger = logging.getLogger(__name__)


@frappe.whitelist()
@rate_limit(max_calls=5, time_window=60)  # 5 requests per minute
def reveal_password(doctype: str, docname: str, fieldname: str) -> Optional[str]:
	"""
	Reveal an encrypted password field with comprehensive security checks.
	
	This function performs multiple security validations before revealing
	a password, including:
	- Input validation
	- User authorization (trusted user check)
	- DocType whitelist verification
	- Document access permissions
	- Comprehensive audit logging
	
	Args:
		doctype: The DocType name
		docname: The document name
		fieldname: The password field name
		
	Returns:
		Decrypted password string, or empty string if no password exists
		
	Raises:
		ValidationError: If input parameters are invalid
		PermissionError: If user is not authorized
		
	Example:
		password = reveal_password("User", "Administrator", "api_key")
	"""
	user = frappe.session.user
	
	try:
		# Step 1: Input Validation
		_validate_inputs(doctype, docname, fieldname)
		
		# Step 2: Verify user is trusted
		if not _is_trusted_user(user):
			logger.warning(f"Unauthorized reveal attempt by {user}")
			raise PermissionError(_("You are not authorized to reveal passwords."))
		
		# Step 3: Verify DocType is in allowed list
		if not _is_doctype_allowed(doctype):
			logger.warning(f"Reveal attempt on non-whitelisted DocType: {doctype} by {user}")
			raise PermissionError(
				_("Password reveal is not enabled for {0}").format(doctype)
			)
		
		# Step 4: Verify document exists and user has read access
		if not frappe.db.exists(doctype, docname):
			raise ValidationError(_("Document {0} not found").format(docname))
		
		if not frappe.has_permission(doctype, "read", docname):
			raise PermissionError(
				_("You do not have permission to access this document")
			)
		
		# Step 5: Get encrypted password
		encrypted = frappe.db.get_value(doctype, docname, fieldname)
		if not encrypted:
			# Log successful reveal (even though password is empty)
			log_password_reveal(
				user=user,
				doctype=doctype,
				docname=docname,
				fieldname=fieldname,
				success=True,
				additional_data={"note": "Password field is empty"}
			)
			return ""
		
		# Step 6: Decrypt password
		password = get_decrypted_password(
			doctype, docname, fieldname, raise_exception=False
		)
		
		# Step 7: Log successful reveal
		log_password_reveal(
			user=user,
			doctype=doctype,
			docname=docname,
			fieldname=fieldname,
			success=True
		)
		
		# Step 8: Send notification (if enabled)
		# TODO: Implement notification system
		# _send_reveal_notification(user, doctype, docname, fieldname)
		
		logger.info(
			f"Password revealed successfully: {doctype}/{docname}/{fieldname} by {user}"
		)
		
		return password
		
	except (ValidationError, PermissionError) as e:
		# Log failed attempt
		log_password_reveal(
			user=user,
			doctype=doctype,
			docname=docname,
			fieldname=fieldname,
			success=False,
			error=str(e)
		)
		raise
		
	except Exception as e:
		# Log unexpected errors
		logger.exception(f"Unexpected error in reveal_password: {str(e)}")
		log_password_reveal(
			user=user,
			doctype=doctype,
			docname=docname,
			fieldname=fieldname,
			success=False,
			error=f"Unexpected error: {str(e)}"
		)
		frappe.throw(
			_("An unexpected error occurred. Please contact your system administrator."),
			title=_("Error")
		)


def _validate_inputs(doctype: str, docname: str, fieldname: str) -> None:
	"""
	Validate input parameters.
	
	Args:
		doctype: DocType name
		docname: Document name
		fieldname: Field name
		
	Raises:
		ValidationError: If any parameter is invalid
	"""
	if not doctype or not isinstance(doctype, str):
		raise ValidationError(_("Invalid DocType"))
	
	if not docname or not isinstance(docname, str):
		raise ValidationError(_("Invalid document name"))
	
	if not fieldname or not isinstance(fieldname, str):
		raise ValidationError(_("Invalid field name"))
	
	# Verify DocType exists
	if not frappe.db.exists("DocType", doctype):
		raise ValidationError(_("DocType {0} does not exist").format(doctype))
	
	# Additional security: prevent SQL injection attempts
	dangerous_chars = ["'", '"', ";", "--", "/*", "*/", "xp_", "sp_"]
	for param in [doctype, docname, fieldname]:
		if any(char in param for char in dangerous_chars):
			logger.error(f"Potential SQL injection attempt detected: {param}")
			raise ValidationError(_("Invalid characters in parameters"))


def _is_trusted_user(user: str) -> bool:
	"""
	Check if a user is in the trusted users list.
	
	Args:
		user: User identifier
		
	Returns:
		True if user is trusted and enabled, False otherwise
	"""
	try:
		return frappe.db.exists("Trusted User", {"user": user, "enabled": 1})
	except Exception as e:
		logger.error(f"Error checking trusted user status: {str(e)}")
		return False


def _is_doctype_allowed(doctype: str) -> bool:
	"""
	Check if a DocType is in the allowed list.
	
	Args:
		doctype: DocType name
		
	Returns:
		True if DocType is allowed and enabled, False otherwise
	"""
	try:
		return frappe.db.exists(
			"Reveal Allowed Doctypes",
			{"doctype_link": doctype, "enabled": 1}
		)
	except Exception as e:
		logger.error(f"Error checking DocType whitelist: {str(e)}")
		return False


@frappe.whitelist()
def check_reveal_permission(doctype: str, docname: str, fieldname: str) -> dict:
	"""
	Check if the current user can reveal a password without actually revealing it.
	
	This is useful for UI to show/hide reveal buttons.
	
	Args:
		doctype: DocType name
		docname: Document name
		fieldname: Field name
		
	Returns:
		Dictionary with permission status and reason
	"""
	user = frappe.session.user
	result = {
		"can_reveal": False,
		"reason": ""
	}
	
	try:
		# Check if user is trusted
		if not _is_trusted_user(user):
			result["reason"] = _("You are not a trusted user")
			return result
		
		# Check if DocType is allowed
		if not _is_doctype_allowed(doctype):
			result["reason"] = _("Password reveal not enabled for this DocType")
			return result
		
		# Check document access
		if not frappe.has_permission(doctype, "read", docname):
			result["reason"] = _("You do not have access to this document")
			return result
		
		result["can_reveal"] = True
		result["reason"] = _("You can reveal this password")
		
	except Exception as e:
		logger.error(f"Error checking reveal permission: {str(e)}")
		result["reason"] = _("Error checking permissions")
	
	return result


@frappe.whitelist()
def get_reveal_info() -> dict:
	"""
	Get information about the current user's reveal capabilities.
	
	Returns:
		Dictionary with user's reveal status and statistics
	"""
	user = frappe.session.user
	
	info = {
		"is_trusted_user": _is_trusted_user(user),
		"allowed_doctypes": [],
		"recent_reveals": 0
	}
	
	if info["is_trusted_user"]:
		# Get allowed DocTypes
		info["allowed_doctypes"] = frappe.get_all(
			"Reveal Allowed Doctypes",
			filters={"enabled": 1},
			pluck="doctype_link"
		)
		
		# Get count of recent reveals (last 24 hours)
		from frappe.utils import add_to_date, now
		yesterday = add_to_date(now(), days=-1)
		
		info["recent_reveals"] = frappe.db.count(
			"Password Reveal Log",
			filters={
				"user": user,
				"success": 1,
				"timestamp": [">=", yesterday]
			}
		)
	
	return info
