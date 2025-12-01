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
		_send_reveal_notification(user, doctype, docname, fieldname)
		
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


def _send_reveal_notification(user: str, doctype: str, docname: str, fieldname: str) -> None:
	"""
	Send notification about password reveal.
	
	Args:
		user: User who revealed the password
		doctype: DocType of the document
		docname: Name of the document
		fieldname: Name of the field
	"""
	try:
		# Check settings
		settings = frappe.get_single("Password Reveal Settings")
		if not settings.enable_notifications:
			return
			
		if not settings.notify_on_success:
			return

		# Create notification log
		subject = f"Security Alert: Password Revealed in {doctype}"
		
		# Prepare context for template
		context = {
			"user": user,
			"doctype": doctype,
			"docname": docname,
			"fieldname": fieldname,
			"time": frappe.utils.format_datetime(frappe.utils.now(), "medium"),
			"ip_address": frappe.local.request_ip if hasattr(frappe.local, "request_ip") else "Unknown",
			"year": frappe.utils.now_datetime().year
		}
		
		# Render HTML message
		message = frappe.render_template(
			"reveal_password/templates/emails/password_reveal_notification.html",
			context
		)
		
		recipients = settings.notification_recipients or ""
		
		# Create notification document
		notification = frappe.get_doc({
			"doctype": "Password Reveal Notification",
			"subject": subject,
			"recipient": recipients,
			"status": "Sent",
			"type": "System",
			"message": message
		})
		notification.insert(ignore_permissions=True)
		
		# Send email if recipients exist
		if recipients:
			frappe.sendmail(
				recipients=recipients.split(","),
				subject=subject,
				message=message,
				now=True
			)
			
		logger.info(f"Notification sent for reveal by {user}")
		
	except Exception as e:
		logger.error(f"Error sending reveal notification: {str(e)}")


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


@frappe.whitelist()
def verify_mfa_token(token: str) -> bool:
	"""
	Verify MFA token for the current user.
	
	Args:
		token: The MFA token to verify
		
	Returns:
		True if token is valid, False otherwise
	"""
	try:
		settings = frappe.get_single("Password Reveal Settings")
		if not settings.enable_mfa:
			return True
			
		# Placeholder for actual MFA verification logic
		# In a real implementation, this would verify against a TOTP secret or email code
		# For now, we'll accept any non-empty token if MFA is enabled, 
		# or just return True to avoid blocking during development
		if not token:
			return False
			
		return True
	except Exception as e:
		logger.error(f"Error verifying MFA token: {str(e)}")
		return False


@frappe.whitelist()
def has_field_permission(doctype: str, fieldname: str, user: str = None) -> bool:
	"""
	Check if user has specific permission for a field.
	
	Args:
		doctype: DocType name
		fieldname: Field name
		user: User to check (defaults to current user)
		
	Returns:
		True if user has permission, False otherwise
	"""
	if not user:
		user = frappe.session.user
		
	try:
		# Get user roles
		roles = frappe.get_roles(user)
		
		# Check Field Permission Matrix
		# We look for any rule that matches the DocType and Field for the user's roles
		# If 'can_reveal' is checked in any matching rule, we allow it
		
		# If no rules exist for this field, we default to True (allow)
		# This ensures backward compatibility
		has_rules = frappe.db.exists("Field Permission Matrix", {
			"doctype_name": doctype,
			"field_name": fieldname
		})
		
		if not has_rules:
			return True
			
		# Check if any of the user's roles allow reveal
		allowed = frappe.db.sql("""
			SELECT 1 FROM `tabField Permission Matrix`
			WHERE doctype_name = %s 
			AND field_name = %s 
			AND role IN %s 
			AND can_reveal = 1
			LIMIT 1
		""", (doctype, fieldname, tuple(roles)))
		
		return bool(allowed)
		
	except Exception as e:
		logger.error(f"Error checking field permission: {str(e)}")
		return False


@frappe.whitelist()
def get_reveal_statistics(period: str = "monthly") -> dict:
	"""
	Get system-wide reveal statistics.
	
	Args:
		period: Time period ('daily', 'weekly', 'monthly')
		
	Returns:
		Dictionary with reveal statistics
	"""
	from frappe.utils import add_to_date, now_date, getdate
	
	# Determine date range
	if period == "daily":
		days = 1
	elif period == "weekly":
		days = 7
	else:
		days = 30
		
	start_date = add_to_date(now_date(), days=-days)
	
	# 1. Basic Stats
	total_reveals = frappe.db.count("Password Reveal Log", filters={"timestamp": [">=", start_date]})
	successful_reveals = frappe.db.count("Password Reveal Log", filters={"timestamp": [">=", start_date], "success": 1})
	failed_attempts = total_reveals - successful_reveals
	
	success_rate = 0
	if total_reveals > 0:
		success_rate = round((successful_reveals / total_reveals) * 100, 1)
		
	active_users = frappe.db.count("Password Reveal Log", filters={"timestamp": [">=", start_date]}, distinct=True, pluck="user")
	
	# 2. Trend Data (Last 'days' days)
	trend_data = frappe.db.sql("""
		SELECT DATE(timestamp) as date, COUNT(*) as count
		FROM `tabPassword Reveal Log`
		WHERE timestamp >= %s
		GROUP BY DATE(timestamp)
		ORDER BY date ASC
	""", (start_date,), as_dict=True)
	
	trend_labels = []
	trend_values = []
	
	# Fill in missing dates
	current_date = getdate(start_date)
	end_date = getdate(now_date())
	
	date_map = {str(d.date): d.count for d in trend_data}
	
	while current_date <= end_date:
		date_str = str(current_date)
		trend_labels.append(current_date.strftime("%d-%b"))
		trend_values.append(date_map.get(date_str, 0))
		current_date = add_to_date(current_date, days=1)

	# 3. DocType Distribution
	doctype_dist = frappe.db.sql("""
		SELECT revealed_doctype, COUNT(*) as count
		FROM `tabPassword Reveal Log`
		WHERE timestamp >= %s
		GROUP BY revealed_doctype
		ORDER BY count DESC
		LIMIT 5
	""", (start_date,), as_dict=True)
	
	doctype_labels = [d.revealed_doctype for d in doctype_dist]
	doctype_values = [d.count for d in doctype_dist]
	
	# 4. Recent Activity
	recent_activity = frappe.get_all(
		"Password Reveal Log",
		fields=["user", "revealed_doctype as doctype", "document_name as docname", "timestamp", "success"],
		order_by="timestamp desc",
		limit=10
	)

	return {
		"total_reveals": total_reveals,
		"successful_reveals": successful_reveals,
		"failed_attempts": failed_attempts,
		"success_rate": success_rate,
		"active_users": active_users,
		"trend_labels": trend_labels,
		"trend_values": trend_values,
		"doctype_labels": doctype_labels,
		"doctype_values": doctype_values,
		"recent_activity": recent_activity,
		"period": period
	}
