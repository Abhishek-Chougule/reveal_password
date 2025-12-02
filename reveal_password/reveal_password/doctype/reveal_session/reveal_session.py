# Copyright (c) 2025, Abhishek Chougule and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import hashlib
import json
from frappe.utils import now


class RevealSession(Document):
	def before_insert(self):
		"""Set timestamp and calculate anomaly score before inserting."""
		if not self.timestamp:
			self.timestamp = now()
		
		# Calculate anomaly score
		self.calculate_anomaly_score()
	
	def calculate_anomaly_score(self):
		"""
		Calculate anomaly score based on various factors.
		Score ranges from 0 (normal) to 100 (highly suspicious).
		"""
		score = 0
		reasons = []
		
		# Check 1: Unusual time (outside business hours)
		from frappe.utils import get_datetime
		dt = get_datetime(self.timestamp)
		hour = dt.hour
		
		if hour < 6 or hour > 22:
			score += 20
			reasons.append(f"Unusual time: {hour}:00")
		
		# Check 2: New IP address for user
		if self.ip_address:
			recent_ips = frappe.db.sql("""
				SELECT DISTINCT ip_address 
				FROM `tabReveal Session`
				WHERE user = %s 
				AND name != %s
				ORDER BY timestamp DESC
				LIMIT 10
			""", (self.user, self.name or ''), as_list=True)
			
			recent_ips = [ip[0] for ip in recent_ips if ip[0]]
			
			if recent_ips and self.ip_address not in recent_ips:
				score += 30
				reasons.append("New IP address")
		
		# Check 3: Rapid successive reveals
		recent_count = frappe.db.count("Reveal Session", filters={
			"user": self.user,
			"timestamp": [">", frappe.utils.add_to_date(now(), minutes=-5)]
		})
		
		if recent_count > 5:
			score += 25
			reasons.append(f"Rapid reveals: {recent_count} in 5 minutes")
		
		# Check 4: Different device fingerprint
		if self.device_fingerprint:
			recent_devices = frappe.db.sql("""
				SELECT DISTINCT device_fingerprint 
				FROM `tabReveal Session`
				WHERE user = %s 
				AND device_fingerprint IS NOT NULL
				AND name != %s
				ORDER BY timestamp DESC
				LIMIT 5
			""", (self.user, self.name or ''), as_list=True)
			
			recent_devices = [d[0] for d in recent_devices if d[0]]
			
			if recent_devices and self.device_fingerprint not in recent_devices:
				score += 15
				reasons.append("New device")
		
		# Check 5: Failed attempt
		if not self.success:
			score += 10
			reasons.append("Failed attempt")
		
		self.anomaly_score = min(score, 100)
		self.is_suspicious = 1 if score >= 50 else 0
		self.anomaly_reasons = "\n".join(reasons) if reasons else None


@frappe.whitelist()
def track_reveal_session(user, doctype, docname, fieldname, success=True, additional_data=None):
	"""
	Track a password reveal session with enhanced metadata.
	
	Args:
		user: User who revealed the password
		doctype: DocType of the document
		docname: Name of the document
		fieldname: Field name
		success: Whether the reveal was successful
		additional_data: Additional metadata
	"""
	try:
		# Get request metadata
		ip_address = frappe.local.request_ip if hasattr(frappe.local, 'request_ip') else None
		user_agent = None
		
		if hasattr(frappe.local, 'request') and frappe.local.request:
			user_agent = frappe.local.request.headers.get('User-Agent', '')
		
		# Get session ID
		session_id = frappe.session.sid
		
		# Generate device fingerprint
		device_fingerprint = generate_device_fingerprint(user_agent, ip_address)
		
		# Get geolocation (basic implementation)
		geolocation = get_geolocation(ip_address)
		
		# Create session record
		session = frappe.get_doc({
			"doctype": "Reveal Session",
			"user": user,
			"session_id": session_id,
			"doctype_revealed": doctype,
			"document_name": docname,
			"field_name": fieldname,
			"ip_address": ip_address,
			"user_agent": user_agent,
			"device_fingerprint": device_fingerprint,
			"geolocation": geolocation,
			"success": 1 if success else 0,
			"timestamp": now()
		})
		
		session.insert(ignore_permissions=True)
		frappe.db.commit()
		
		# Check if suspicious and alert
		if session.is_suspicious:
			alert_suspicious_activity(session)
		
		return session.name
		
	except Exception as e:
		frappe.log_error(f"Error tracking reveal session: {str(e)}", "Session Tracking Error")
		return None


def generate_device_fingerprint(user_agent, ip_address):
	"""
	Generate a device fingerprint based on user agent and IP.
	
	Args:
		user_agent: Browser user agent string
		ip_address: IP address
		
	Returns:
		Device fingerprint hash
	"""
	if not user_agent and not ip_address:
		return None
	
	fingerprint_data = f"{user_agent or ''}{ip_address or ''}"
	return hashlib.md5(fingerprint_data.encode()).hexdigest()[:16]


def get_geolocation(ip_address):
	"""
	Get approximate geolocation from IP address.
	
	Args:
		ip_address: IP address
		
	Returns:
		Geolocation string (JSON format)
	"""
	if not ip_address or ip_address.startswith('127.') or ip_address.startswith('192.168.'):
		return json.dumps({"type": "local", "ip": ip_address})
	
	# Placeholder for actual geolocation service
	# In production, integrate with services like ipapi.co, ipstack, etc.
	return json.dumps({
		"ip": ip_address,
		"type": "external",
		"note": "Geolocation service not configured"
	})


def alert_suspicious_activity(session):
	"""
	Alert administrators about suspicious activity.
	
	Args:
		session: Reveal Session document
	"""
	try:
		# Get notification recipients from settings
		settings = frappe.get_single("Password Reveal Settings")
		
		if not settings.enable_notifications or not settings.notification_recipients:
			return
		
		subject = f"⚠️ Suspicious Password Reveal Activity Detected"
		message = f"""
		<h3>Suspicious Activity Alert</h3>
		<p>A potentially suspicious password reveal attempt has been detected:</p>
		
		<table style="border-collapse: collapse; width: 100%;">
			<tr>
				<td style="padding: 8px; border: 1px solid #ddd;"><strong>User:</strong></td>
				<td style="padding: 8px; border: 1px solid #ddd;">{session.user}</td>
			</tr>
			<tr>
				<td style="padding: 8px; border: 1px solid #ddd;"><strong>DocType:</strong></td>
				<td style="padding: 8px; border: 1px solid #ddd;">{session.doctype_revealed}</td>
			</tr>
			<tr>
				<td style="padding: 8px; border: 1px solid #ddd;"><strong>Document:</strong></td>
				<td style="padding: 8px; border: 1px solid #ddd;">{session.document_name}</td>
			</tr>
			<tr>
				<td style="padding: 8px; border: 1px solid #ddd;"><strong>IP Address:</strong></td>
				<td style="padding: 8px; border: 1px solid #ddd;">{session.ip_address}</td>
			</tr>
			<tr>
				<td style="padding: 8px; border: 1px solid #ddd;"><strong>Anomaly Score:</strong></td>
				<td style="padding: 8px; border: 1px solid #ddd;">{session.anomaly_score}/100</td>
			</tr>
			<tr>
				<td style="padding: 8px; border: 1px solid #ddd;"><strong>Reasons:</strong></td>
				<td style="padding: 8px; border: 1px solid #ddd;">{session.anomaly_reasons or 'N/A'}</td>
			</tr>
			<tr>
				<td style="padding: 8px; border: 1px solid #ddd;"><strong>Time:</strong></td>
				<td style="padding: 8px; border: 1px solid #ddd;">{session.timestamp}</td>
			</tr>
		</table>
		
		<p style="margin-top: 20px;">
			<strong>Action Required:</strong> Please review this activity and take appropriate action if necessary.
		</p>
		"""
		
		frappe.sendmail(
			recipients=settings.notification_recipients.split(","),
			subject=subject,
			message=message,
			now=True
		)
		
	except Exception as e:
		frappe.log_error(f"Error sending suspicious activity alert: {str(e)}")


@frappe.whitelist()
def get_user_session_history(user=None, limit=50):
	"""
	Get session history for a user.
	
	Args:
		user: User to get history for (defaults to current user)
		limit: Maximum number of records
		
	Returns:
		List of session records
	"""
	if not user:
		user = frappe.session.user
	
	return frappe.get_all(
		"Reveal Session",
		filters={"user": user},
		fields=["name", "doctype_revealed", "document_name", "ip_address", 
		        "timestamp", "success", "is_suspicious", "anomaly_score"],
		order_by="timestamp desc",
		limit=limit
	)


@frappe.whitelist()
def get_suspicious_sessions(days=7):
	"""
	Get all suspicious sessions in the last N days.
	
	Args:
		days: Number of days to look back
		
	Returns:
		List of suspicious sessions
	"""
	from_date = frappe.utils.add_to_date(now(), days=-days)
	
	return frappe.get_all(
		"Reveal Session",
		filters={
			"is_suspicious": 1,
			"timestamp": [">=", from_date]
		},
		fields=["name", "user", "doctype_revealed", "document_name", "ip_address",
		        "timestamp", "anomaly_score", "anomaly_reasons"],
		order_by="anomaly_score desc, timestamp desc"
	)
