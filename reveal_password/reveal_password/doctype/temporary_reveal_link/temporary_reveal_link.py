# Copyright (c) 2025, Abhishek Chougule and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now, add_to_date, get_datetime
from frappe.utils.password import get_decrypted_password
import secrets
import hashlib


class TemporaryRevealLink(Document):
	def before_insert(self):
		"""Generate link ID and access token before inserting."""
		if not self.link_id:
			self.link_id = generate_link_id()
		
		if not self.access_token:
			self.access_token = generate_access_token()
		
		if not self.created_at:
			self.created_at = now()
		
		if not self.created_by:
			self.created_by = frappe.session.user
		
		# Fetch and store the password value
		if not self.password_value:
			self.password_value = get_decrypted_password(
				self.doctype_revealed,
				self.document_name,
				self.field_name,
				raise_exception=False
			)
	
	def validate(self):
		"""Validate the link before saving."""
		# Ensure expiration is in the future
		if get_datetime(self.expires_at) <= get_datetime(now()):
			frappe.throw("Expiration time must be in the future")
		
		# Ensure max_uses is positive
		if self.max_uses < 1:
			frappe.throw("Max uses must be at least 1")
	
	def is_valid(self):
		"""
		Check if the link is still valid.
		
		Returns:
			Tuple of (is_valid, reason)
		"""
		if not self.is_active:
			return False, "Link has been revoked"
		
		if get_datetime(self.expires_at) <= get_datetime(now()):
			return False, "Link has expired"
		
		if self.current_uses >= self.max_uses:
			return False, "Link usage limit reached"
		
		return True, "Valid"
	
	def increment_usage(self, accessed_by=None):
		"""
		Increment the usage counter and update last access info.
		
		Args:
			accessed_by: IP address or identifier of accessor
		"""
		self.current_uses += 1
		self.last_accessed_at = now()
		self.last_accessed_by = accessed_by or "Unknown"
		
		# Deactivate if max uses reached
		if self.current_uses >= self.max_uses:
			self.is_active = 0
		
		self.save(ignore_permissions=True)
		frappe.db.commit()


def generate_link_id():
	"""Generate a unique link ID."""
	return secrets.token_urlsafe(16)


def generate_access_token():
	"""Generate a secure access token."""
	return secrets.token_urlsafe(32)


@frappe.whitelist()
def create_temporary_link(doctype, docname, fieldname, expires_in_hours=24, max_uses=1):
	"""
	Create a temporary reveal link.
	
	Args:
		doctype: DocType of the document
		docname: Name of the document
		fieldname: Field name
		expires_in_hours: Hours until expiration (default 24)
		max_uses: Maximum number of uses (default 1)
		
	Returns:
		Dictionary with link details
	"""
	# Verify user has permission to reveal this password
	if not frappe.has_permission(doctype, "read", docname):
		frappe.throw("You do not have permission to access this document")
	
	# Check if user is trusted
	from reveal_password.reveal import _is_trusted_user
	if not _is_trusted_user(frappe.session.user):
		frappe.throw("You are not authorized to create reveal links")
	
	# Calculate expiration
	expires_at = add_to_date(now(), hours=int(expires_in_hours))
	
	# Create link
	link = frappe.get_doc({
		"doctype": "Temporary Reveal Link",
		"doctype_revealed": doctype,
		"document_name": docname,
		"field_name": fieldname,
		"expires_at": expires_at,
		"max_uses": int(max_uses)
	})
	
	link.insert(ignore_permissions=True)
	frappe.db.commit()
	
	# Generate shareable URL
	site_url = frappe.utils.get_url()
	reveal_url = f"{site_url}/reveal-link/{link.link_id}?token={link.access_token}"
	
	# Log the creation
	frappe.logger().info(f"Temporary reveal link created: {link.name} by {frappe.session.user}")
	
	return {
		"link_id": link.link_id,
		"url": reveal_url,
		"expires_at": link.expires_at,
		"max_uses": link.max_uses,
		"qr_code": generate_qr_code(reveal_url)
	}


@frappe.whitelist(allow_guest=True)
def access_temporary_link(link_id, token):
	"""
	Access a temporary reveal link.
	
	Args:
		link_id: Link ID
		token: Access token
		
	Returns:
		Dictionary with password or error
	"""
	try:
		# Find the link
		link = frappe.get_doc("Temporary Reveal Link", {"link_id": link_id})
		
		# Verify token
		if link.access_token != token:
			frappe.throw("Invalid access token")
		
		# Check if valid
		is_valid, reason = link.is_valid()
		if not is_valid:
			frappe.throw(reason)
		
		# Get accessor info
		accessed_by = frappe.local.request_ip if hasattr(frappe.local, 'request_ip') else "Unknown"
		
		# Increment usage
		link.increment_usage(accessed_by)
		
		# Log access
		log_link_access(link, accessed_by, success=True)
		
		return {
			"success": True,
			"password": link.password_value,
			"doctype": link.doctype_revealed,
			"document": link.document_name,
			"field": link.field_name,
			"uses_remaining": link.max_uses - link.current_uses,
			"expires_at": link.expires_at
		}
		
	except Exception as e:
		# Log failed access
		if 'link' in locals():
			log_link_access(link, accessed_by if 'accessed_by' in locals() else "Unknown", success=False, error=str(e))
		
		return {
			"success": False,
			"error": str(e)
		}


@frappe.whitelist()
def revoke_link(link_id):
	"""
	Revoke a temporary link.
	
	Args:
		link_id: Link ID to revoke
	"""
	link = frappe.get_doc("Temporary Reveal Link", {"link_id": link_id})
	
	# Check if user is owner or has permission
	if link.created_by != frappe.session.user and not frappe.has_permission("Temporary Reveal Link", "write"):
		frappe.throw("You do not have permission to revoke this link")
	
	link.is_active = 0
	link.save(ignore_permissions=True)
	frappe.db.commit()
	
	frappe.logger().info(f"Temporary reveal link revoked: {link.name} by {frappe.session.user}")
	
	return {"success": True, "message": "Link revoked successfully"}


@frappe.whitelist()
def get_my_links(limit=50):
	"""
	Get links created by the current user.
	
	Args:
		limit: Maximum number of links to return
		
	Returns:
		List of links
	"""
	return frappe.get_all(
		"Temporary Reveal Link",
		filters={"created_by": frappe.session.user},
		fields=["name", "link_id", "doctype_revealed", "document_name", "field_name",
		        "created_at", "expires_at", "is_active", "max_uses", "current_uses"],
		order_by="created_at desc",
		limit=limit
	)


def log_link_access(link, accessed_by, success=True, error=None):
	"""
	Log an access attempt to a temporary link.
	
	Args:
		link: Temporary Reveal Link document
		accessed_by: IP address or identifier
		success: Whether access was successful
		error: Error message if failed
	"""
	try:
		# Add to access logs child table
		link.append("access_logs", {
			"accessed_at": now(),
			"accessed_by": accessed_by,
			"ip_address": accessed_by, # Assuming accessed_by is IP for now
			"success": 1 if success else 0,
			"error_message": error
		})
		
		# We need to save the link doc to persist the child table row
		# But we must be careful not to trigger recursion or validation errors if called from within a save
		# Since this is usually called after access, it should be fine.
		# However, if called from access_temporary_link which saves usage, we might want to avoid double save.
		# In access_temporary_link, we call increment_usage which saves.
		# Let's check if we can just append and let the caller save, or save here.
		
		# Since access_temporary_link calls this *after* increment_usage (which saves),
		# we need to save again.
		link.save(ignore_permissions=True)
		
	except Exception as e:
		frappe.log_error(f"Error logging link access: {str(e)}")


def generate_qr_code(url):
	"""
	Generate QR code for the URL.
	
	Args:
		url: URL to encode
		
	Returns:
		Base64 encoded QR code image
	"""
	try:
		import qrcode
		import io
		import base64
		
		qr = qrcode.QRCode(version=1, box_size=10, border=5)
		qr.add_data(url)
		qr.make(fit=True)
		
		img = qr.make_image(fill_color="black", back_color="white")
		
		buffer = io.BytesIO()
		img.save(buffer, format='PNG')
		img_str = base64.b64encode(buffer.getvalue()).decode()
		
		return f"data:image/png;base64,{img_str}"
	except Exception as e:
		frappe.logger().error(f"Error generating QR code: {str(e)}")
		return None


# Scheduled task to cleanup expired links
def cleanup_expired_links():
	"""Clean up expired links (run daily)."""
	expired_links = frappe.get_all(
		"Temporary Reveal Link",
		filters={
			"expires_at": ["<", now()],
			"is_active": 1
		},
		pluck="name"
	)
	
	for link_name in expired_links:
		link = frappe.get_doc("Temporary Reveal Link", link_name)
		link.is_active = 0
		link.save(ignore_permissions=True)
	
	frappe.db.commit()
	
	if expired_links:
		frappe.logger().info(f"Cleaned up {len(expired_links)} expired links")
