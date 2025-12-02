# Copyright (c) 2025, Abhishek Chougule and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now_datetime

def check_and_rotate_passwords():
	"""
	Scheduled job to check for password rotation policies that are due.
	"""
	now = now_datetime()
	
	# Find policies that are enabled and due for rotation
	policies = frappe.get_all(
		"Password Rotation Policy",
		filters={
			"enabled": 1,
			"next_rotation": ["<=", now]
		},
		pluck="name"
	)
	
	results = []
	for policy_name in policies:
		try:
			policy = frappe.get_doc("Password Rotation Policy", policy_name)
			success, failed = policy.execute_rotation()
			
			results.append({
				"policy": policy_name,
				"success": success,
				"failed": failed
			})
			
			# Send notification if configured
			if policy.notification_email:
				send_rotation_notification(policy, success, failed)
				
		except Exception as e:
			frappe.log_error(f"Error executing rotation for policy {policy_name}: {str(e)}")
	
	return results

def send_rotation_notification(policy, success_count, failure_count):
	"""
	Send email notification about rotation results.
	"""
	subject = f"Password Rotation Report: {policy.policy_name}"
	message = f"""
	<h3>Password Rotation Completed</h3>
	<p><strong>Policy:</strong> {policy.policy_name}</p>
	<p><strong>Target:</strong> {policy.target_doctype} ({policy.target_field})</p>
	<br>
	<table border="1" cellpadding="5" style="border-collapse: collapse;">
		<tr>
			<th>Status</th>
			<th>Count</th>
		</tr>
		<tr>
			<td style="color: green;">Success</td>
			<td>{success_count}</td>
		</tr>
		<tr>
			<td style="color: red;">Failed</td>
			<td>{failure_count}</td>
		</tr>
	</table>
	<br>
	<p>Please check the Password Rotation History for details.</p>
	"""
	
	frappe.sendmail(
		recipients=[policy.notification_email],
		subject=subject,
		message=message,
		now=True
	)
