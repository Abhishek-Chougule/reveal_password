# Copyright (c) 2025, Abhishek Chougule and contributors
# For license information, please see license.txt

"""
Audit logging utilities for password reveal operations.

This module provides functions for creating comprehensive audit logs
of all password reveal attempts, successful or failed.
"""

import frappe
from frappe.utils import now, get_datetime
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def log_password_reveal(
	user: str,
	doctype: str,
	docname: str,
	fieldname: str,
	success: bool,
	error: Optional[str] = None,
	additional_data: Optional[Dict[str, Any]] = None
) -> None:
	"""
	Create an audit log entry for a password reveal attempt.
	
	This function creates a comprehensive audit trail of all password
	reveal attempts, including metadata like IP address, user agent,
	and geolocation.
	
	Args:
		user: User who attempted to reveal the password
		doctype: DocType of the document
		docname: Name of the document
		fieldname: Name of the password field
		success: Whether the reveal was successful
		error: Error message if reveal failed
		additional_data: Additional metadata to log
		
	Example:
		log_password_reveal(
			user="user@example.com",
			doctype="User",
			docname="Administrator",
			fieldname="api_key",
			success=True
		)
	"""
	try:
		# Prepare log data
		log_data = {
			"doctype": "Password Reveal Log",
			"user": user,
			"revealed_doctype": doctype,
			"document_name": docname,
			"field_name": fieldname,
			"success": 1 if success else 0,
			"error_message": error or "",
			"timestamp": now(),
		}
		
		# Add request metadata if available
		if hasattr(frappe.local, "request_ip"):
			log_data["ip_address"] = frappe.local.request_ip
			
		if hasattr(frappe.local, "request") and frappe.local.request:
			log_data["user_agent"] = frappe.local.request.headers.get("User-Agent", "")
			
		# Add any additional data
		if additional_data:
			log_data.update(additional_data)
		
		# Create log document
		log_doc = frappe.get_doc(log_data)
		log_doc.insert(ignore_permissions=True)
		frappe.db.commit()
		
		logger.info(
			f"Password reveal {'successful' if success else 'failed'}: "
			f"{doctype}/{docname}/{fieldname} by {user}"
		)
		
	except Exception as e:
		# Don't let logging failures break the main flow
		logger.error(f"Failed to create audit log: {str(e)}")
		frappe.log_error(
			f"Audit logging error: {str(e)}\nUser: {user}\nDocType: {doctype}\nDocument: {docname}",
			"Audit Log Error"
		)


def get_user_reveal_history(
	user: str,
	limit: int = 50,
	from_date: Optional[str] = None,
	to_date: Optional[str] = None
) -> list:
	"""
	Get password reveal history for a specific user.
	
	Args:
		user: User identifier
		limit: Maximum number of records to return
		from_date: Start date for filtering (optional)
		to_date: End date for filtering (optional)
		
	Returns:
		List of reveal log entries
	"""
	filters = {"user": user}
	
	if from_date:
		filters["timestamp"] = [">=", from_date]
	if to_date:
		if "timestamp" in filters:
			filters["timestamp"] = ["between", [from_date, to_date]]
		else:
			filters["timestamp"] = ["<=", to_date]
	
	return frappe.get_all(
		"Password Reveal Log",
		filters=filters,
		fields=[
			"name",
			"revealed_doctype",
			"document_name",
			"field_name",
			"success",
			"error_message",
			"timestamp",
			"ip_address"
		],
		order_by="timestamp desc",
		limit=limit
	)


def get_document_reveal_history(doctype: str, docname: str, limit: int = 50) -> list:
	"""
	Get password reveal history for a specific document.
	
	Args:
		doctype: DocType name
		docname: Document name
		limit: Maximum number of records to return
		
	Returns:
		List of reveal log entries
	"""
	return frappe.get_all(
		"Password Reveal Log",
		filters={
			"revealed_doctype": doctype,
			"document_name": docname
		},
		fields=[
			"name",
			"user",
			"field_name",
			"success",
			"error_message",
			"timestamp",
			"ip_address"
		],
		order_by="timestamp desc",
		limit=limit
	)


def get_failed_attempts(
	hours: int = 24,
	min_attempts: int = 3
) -> list:
	"""
	Get users with multiple failed reveal attempts.
	
	This is useful for identifying potential security threats.
	
	Args:
		hours: Number of hours to look back
		min_attempts: Minimum number of failed attempts to flag
		
	Returns:
		List of users with failed attempts count
	"""
	from_time = get_datetime() - frappe.utils.datetime.timedelta(hours=hours)
	
	failed_attempts = frappe.db.sql(
		"""
		SELECT 
			user,
			COUNT(*) as attempt_count,
			MAX(timestamp) as last_attempt,
			GROUP_CONCAT(DISTINCT ip_address) as ip_addresses
		FROM `tabPassword Reveal Log`
		WHERE success = 0
			AND timestamp >= %s
		GROUP BY user
		HAVING attempt_count >= %s
		ORDER BY attempt_count DESC
		""",
		(from_time, min_attempts),
		as_dict=True
	)
	
	return failed_attempts


def get_reveal_statistics(days: int = 30) -> Dict[str, Any]:
	"""
	Get aggregated statistics for password reveals.
	
	Args:
		days: Number of days to analyze
		
	Returns:
		Dictionary with statistics
	"""
	from_date = get_datetime() - frappe.utils.datetime.timedelta(days=days)
	
	stats = frappe.db.sql(
		"""
		SELECT 
			COUNT(*) as total_attempts,
			SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
			SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed,
			COUNT(DISTINCT user) as unique_users,
			COUNT(DISTINCT revealed_doctype) as unique_doctypes
		FROM `tabPassword Reveal Log`
		WHERE timestamp >= %s
		""",
		from_date,
		as_dict=True
	)[0]
	
	# Calculate success rate
	if stats.total_attempts > 0:
		stats["success_rate"] = (stats.successful / stats.total_attempts) * 100
	else:
		stats["success_rate"] = 0
	
	return stats


def cleanup_old_logs(retention_days: int = 90) -> int:
	"""
	Delete audit logs older than the specified retention period.
	
	Args:
		retention_days: Number of days to retain logs
		
	Returns:
		Number of logs deleted
	"""
	cutoff_date = get_datetime() - frappe.utils.datetime.timedelta(days=retention_days)
	
	old_logs = frappe.get_all(
		"Password Reveal Log",
		filters={"timestamp": ["<", cutoff_date]},
		pluck="name"
	)
	
	for log_name in old_logs:
		frappe.delete_doc("Password Reveal Log", log_name, ignore_permissions=True)
	
	frappe.db.commit()
	
	logger.info(f"Cleaned up {len(old_logs)} old audit logs")
	return len(old_logs)


@frappe.whitelist()
def get_my_reveal_history(limit: int = 50):
	"""
	Get password reveal history for the current user.
	
	This is a whitelisted method that users can call to see their own history.
	
	Args:
		limit: Maximum number of records to return
		
	Returns:
		List of reveal log entries
	"""
	return get_user_reveal_history(frappe.session.user, limit=limit)
