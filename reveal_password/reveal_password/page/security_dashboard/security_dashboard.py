# Copyright (c) 2025, Abhishek Chougule and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now, add_to_date, getdate
import json


@frappe.whitelist()
def get_security_metrics(days=7):
	"""
	Get comprehensive security metrics for the dashboard.
	
	Args:
		days: Number of days to analyze
		
	Returns:
		Dictionary with all security metrics
	"""
	days = int(days)
	from_date = add_to_date(now(), days=-days)
	
	# Basic metrics
	total_sessions = frappe.db.count("Reveal Session", filters={"timestamp": [">=", from_date]})
	suspicious_count = frappe.db.count("Reveal Session", filters={
		"timestamp": [">=", from_date],
		"is_suspicious": 1
	})
	
	# Unique users
	unique_users = frappe.db.sql("""
		SELECT COUNT(DISTINCT user)
		FROM `tabReveal Session`
		WHERE timestamp >= %s
	""", (from_date,))[0][0]
	
	# Average anomaly score
	avg_anomaly = frappe.db.sql("""
		SELECT AVG(anomaly_score)
		FROM `tabReveal Session`
		WHERE timestamp >= %s AND anomaly_score > 0
	""", (from_date,))[0][0] or 0
	
	# Timeline data
	timeline_data = get_timeline_data(from_date, days)
	
	# Top users
	top_users = get_top_users(from_date)
	
	# Suspicious activities
	suspicious_activities = frappe.get_all(
		"Reveal Session",
		filters={
			"timestamp": [">=", from_date],
			"is_suspicious": 1
		},
		fields=["user", "doctype_revealed", "ip_address", "timestamp", 
		        "anomaly_score", "anomaly_reasons"],
		order_by="anomaly_score desc, timestamp desc",
		limit=20
	)
	
	# Top IPs
	top_ips = get_top_ips(from_date)
	
	# Device stats
	device_stats = get_device_stats(from_date, total_sessions)
	
	# Generate alerts
	alerts = generate_alerts(suspicious_count, total_sessions, avg_anomaly)
	
	return {
		"total_sessions": total_sessions,
		"suspicious_count": suspicious_count,
		"unique_users": unique_users,
		"avg_anomaly_score": avg_anomaly,
		"timeline_labels": timeline_data["labels"],
		"timeline_normal": timeline_data["normal"],
		"timeline_suspicious": timeline_data["suspicious"],
		"top_users_labels": top_users["labels"],
		"top_users_values": top_users["values"],
		"suspicious_activities": suspicious_activities,
		"top_ips": top_ips,
		"device_stats": device_stats,
		"alerts": alerts
	}


def get_timeline_data(from_date, days):
	"""Get timeline data for activity chart."""
	# Get daily counts
	data = frappe.db.sql("""
		SELECT 
			DATE(timestamp) as date,
			SUM(CASE WHEN is_suspicious = 0 THEN 1 ELSE 0 END) as normal,
			SUM(CASE WHEN is_suspicious = 1 THEN 1 ELSE 0 END) as suspicious
		FROM `tabReveal Session`
		WHERE timestamp >= %s
		GROUP BY DATE(timestamp)
		ORDER BY date ASC
	""", (from_date,), as_dict=True)
	
	# Fill in missing dates
	labels = []
	normal = []
	suspicious = []
	
	current_date = getdate(from_date)
	end_date = getdate(now())
	
	date_map = {str(d.date): d for d in data}
	
	while current_date <= end_date:
		date_str = str(current_date)
		labels.append(current_date.strftime("%d-%b"))
		
		if date_str in date_map:
			normal.append(date_map[date_str].normal)
			suspicious.append(date_map[date_str].suspicious)
		else:
			normal.append(0)
			suspicious.append(0)
		
		current_date = add_to_date(current_date, days=1)
	
	return {
		"labels": labels,
		"normal": normal,
		"suspicious": suspicious
	}


def get_top_users(from_date):
	"""Get top users by session count."""
	data = frappe.db.sql("""
		SELECT user, COUNT(*) as count
		FROM `tabReveal Session`
		WHERE timestamp >= %s
		GROUP BY user
		ORDER BY count DESC
		LIMIT 5
	""", (from_date,), as_dict=True)
	
	return {
		"labels": [d.user for d in data],
		"values": [d.count for d in data]
	}


def get_top_ips(from_date):
	"""Get top IP addresses with user information."""
	data = frappe.db.sql("""
		SELECT 
			ip_address,
			COUNT(*) as count,
			GROUP_CONCAT(DISTINCT user) as users
		FROM `tabReveal Session`
		WHERE timestamp >= %s AND ip_address IS NOT NULL
		GROUP BY ip_address
		ORDER BY count DESC
		LIMIT 10
	""", (from_date,), as_dict=True)
	
	for d in data:
		d.users = d.users.split(',') if d.users else []
	
	return data


def get_device_stats(from_date, total_sessions):
	"""Get device type statistics."""
	# Simple device detection from user agent
	data = frappe.db.sql("""
		SELECT user_agent, COUNT(*) as count
		FROM `tabReveal Session`
		WHERE timestamp >= %s AND user_agent IS NOT NULL
		GROUP BY user_agent
	""", (from_date,), as_dict=True)
	
	device_types = {
		"Desktop": 0,
		"Mobile": 0,
		"Tablet": 0,
		"Unknown": 0
	}
	
	for d in data:
		ua = d.user_agent.lower()
		if 'mobile' in ua or 'android' in ua or 'iphone' in ua:
			device_types["Mobile"] += d.count
		elif 'tablet' in ua or 'ipad' in ua:
			device_types["Tablet"] += d.count
		elif ua:
			device_types["Desktop"] += d.count
		else:
			device_types["Unknown"] += d.count
	
	stats = []
	for device_type, count in device_types.items():
		if count > 0:
			percentage = (count / total_sessions * 100) if total_sessions > 0 else 0
			stats.append({
				"device_type": device_type,
				"count": count,
				"percentage": round(percentage, 1)
			})
	
	return sorted(stats, key=lambda x: x["count"], reverse=True)


def generate_alerts(suspicious_count, total_sessions, avg_anomaly):
	"""Generate security alerts based on metrics."""
	alerts = []
	
	# High suspicious activity rate
	if total_sessions > 0:
		suspicious_rate = (suspicious_count / total_sessions) * 100
		
		if suspicious_rate > 20:
			alerts.append({
				"severity": "critical",
				"title": "Critical: High Suspicious Activity Rate",
				"message": f"{suspicious_rate:.1f}% of sessions are flagged as suspicious. Immediate investigation recommended."
			})
		elif suspicious_rate > 10:
			alerts.append({
				"severity": "warning",
				"title": "Warning: Elevated Suspicious Activity",
				"message": f"{suspicious_rate:.1f}% of sessions are flagged as suspicious. Monitor closely."
			})
	
	# High average anomaly score
	if avg_anomaly > 60:
		alerts.append({
			"severity": "critical",
			"title": "Critical: High Anomaly Score",
			"message": f"Average anomaly score is {avg_anomaly:.1f}/100. Review security policies."
		})
	elif avg_anomaly > 40:
		alerts.append({
			"severity": "warning",
			"title": "Warning: Elevated Anomaly Score",
			"message": f"Average anomaly score is {avg_anomaly:.1f}/100. Consider tightening security."
		})
	
	# Check for recent spike
	recent_suspicious = frappe.db.count("Reveal Session", filters={
		"timestamp": [">=", add_to_date(now(), hours=-24)],
		"is_suspicious": 1
	})
	
	if recent_suspicious > 10:
		alerts.append({
			"severity": "warning",
			"title": "Warning: Recent Activity Spike",
			"message": f"{recent_suspicious} suspicious activities in the last 24 hours."
		})
	
	# Info: All clear
	if not alerts:
		alerts.append({
			"severity": "info",
			"title": "All Clear",
			"message": "No significant security concerns detected."
		})
	
	return alerts


@frappe.whitelist()
def export_security_report(days=7):
	"""
	Export security report as CSV.
	
	Args:
		days: Number of days to include
		
	Returns:
		CSV string
	"""
	days = int(days)
	from_date = add_to_date(now(), days=-days)
	
	# Get all sessions
	sessions = frappe.get_all(
		"Reveal Session",
		filters={"timestamp": [">=", from_date]},
		fields=["user", "doctype_revealed", "document_name", "field_name",
		        "ip_address", "timestamp", "success", "is_suspicious",
		        "anomaly_score", "anomaly_reasons"],
		order_by="timestamp desc"
	)
	
	# Generate CSV
	import csv
	from io import StringIO
	
	output = StringIO()
	writer = csv.writer(output)
	
	# Header
	writer.writerow([
		"Timestamp", "User", "DocType", "Document", "Field",
		"IP Address", "Success", "Suspicious", "Anomaly Score", "Reasons"
	])
	
	# Data
	for session in sessions:
		writer.writerow([
			session.timestamp,
			session.user,
			session.doctype_revealed,
			session.document_name,
			session.field_name,
			session.ip_address or "N/A",
			"Yes" if session.success else "No",
			"Yes" if session.is_suspicious else "No",
			session.anomaly_score or 0,
			session.anomaly_reasons or "N/A"
		])
	
	return output.getvalue()


@frappe.whitelist()
def get_compliance_report(days=30):
	"""
	Generate compliance report for auditing.
	
	Args:
		days: Number of days to include
		
	Returns:
		Compliance report data
	"""
	days = int(days)
	from_date = add_to_date(now(), days=-days)
	
	# Total reveals
	total_reveals = frappe.db.count("Password Reveal Log", filters={
		"timestamp": [">=", from_date]
	})
	
	# Successful reveals
	successful_reveals = frappe.db.count("Password Reveal Log", filters={
		"timestamp": [">=", from_date],
		"success": 1
	})
	
	# Failed attempts
	failed_attempts = total_reveals - successful_reveals
	
	# Reveals by user
	by_user = frappe.db.sql("""
		SELECT user, COUNT(*) as count
		FROM `tabPassword Reveal Log`
		WHERE timestamp >= %s
		GROUP BY user
		ORDER BY count DESC
	""", (from_date,), as_dict=True)
	
	# Reveals by DocType
	by_doctype = frappe.db.sql("""
		SELECT revealed_doctype, COUNT(*) as count
		FROM `tabPassword Reveal Log`
		WHERE timestamp >= %s
		GROUP BY revealed_doctype
		ORDER BY count DESC
	""", (from_date,), as_dict=True)
	
	# MFA usage
	mfa_enabled_users = frappe.db.count("MFA Secret", filters={"is_enabled": 1})
	total_users = frappe.db.count("Trusted User", filters={"enabled": 1})
	
	return {
		"period": f"Last {days} days",
		"total_reveals": total_reveals,
		"successful_reveals": successful_reveals,
		"failed_attempts": failed_attempts,
		"success_rate": (successful_reveals / total_reveals * 100) if total_reveals > 0 else 0,
		"by_user": by_user,
		"by_doctype": by_doctype,
		"mfa_adoption": {
			"enabled": mfa_enabled_users,
			"total": total_users,
			"percentage": (mfa_enabled_users / total_users * 100) if total_users > 0 else 0
		}
	}
