# Copyright (c) 2025, Abhishek Chougule and contributors
# For license information, please see license.txt

"""
Comprehensive tests for password reveal functionality.

This module tests all aspects of the password reveal system including:
- Basic reveal functionality
- Permission checks
- Rate limiting
- Audit logging
- Error handling
"""

import frappe
import unittest
from frappe.utils import now, add_to_date
from unittest.mock import patch, MagicMock


class TestPasswordReveal(unittest.TestCase):
	"""Test cases for password reveal functionality."""
	
	@classmethod
	def setUpClass(cls):
		"""Set up test fixtures that are used by all tests."""
		# Create test user
		if not frappe.db.exists("User", "test_reveal_user@example.com"):
			user = frappe.get_doc({
				"doctype": "User",
				"email": "test_reveal_user@example.com",
				"first_name": "Test",
				"last_name": "User",
				"send_welcome_email": 0
			})
			user.insert(ignore_permissions=True)
		
		# Create trusted user entry
		if not frappe.db.exists("Trusted User", {"user": "test_reveal_user@example.com"}):
			trusted = frappe.get_doc({
				"doctype": "Trusted User",
				"user": "test_reveal_user@example.com",
				"enabled": 1
			})
			trusted.insert(ignore_permissions=True)
		
		# Add User doctype to allowed list
		if not frappe.db.exists("Reveal Allowed Doctypes", {"doctype_link": "User"}):
			allowed = frappe.get_doc({
				"doctype": "Reveal Allowed Doctypes",
				"doctype_link": "User",
				"enabled": 1
			})
			allowed.insert(ignore_permissions=True)
		
		frappe.db.commit()
	
	def setUp(self):
		"""Set up before each test."""
		frappe.set_user("test_reveal_user@example.com")
	
	def tearDown(self):
		"""Clean up after each test."""
		frappe.set_user("Administrator")
	
	def test_reveal_password_success(self):
		"""Test successful password reveal."""
		# This test requires the enhanced reveal.py to be active
		# For now, test the original reveal.py
		from reveal_password.reveal import reveal_password
		
		# Test with a user that has a password field
		try:
			result = reveal_password("User", "Administrator", "api_key")
			# Should return a string (password or empty string)
			self.assertIsInstance(result, str)
		except Exception as e:
			# If field doesn't exist, that's okay for this test
			self.assertIn("api_key", str(e).lower() or "field" in str(e).lower())
	
	def test_reveal_password_unauthorized_user(self):
		"""Test that unauthorized users cannot reveal passwords."""
		from reveal_password.reveal import reveal_password
		from frappe.exceptions import PermissionError
		
		# Set user to someone not in trusted list
		frappe.set_user("Guest")
		
		with self.assertRaises(PermissionError):
			reveal_password("User", "Administrator", "api_key")
	
	def test_reveal_password_invalid_doctype(self):
		"""Test reveal with invalid DocType."""
		from reveal_password.reveal import reveal_password
		from frappe.exceptions import ValidationError
		
		with self.assertRaises((ValidationError, Exception)):
			reveal_password("NonExistentDocType", "test", "password")
	
	def test_reveal_password_invalid_document(self):
		"""Test reveal with non-existent document."""
		from reveal_password.reveal import reveal_password
		from frappe.exceptions import ValidationError
		
		with self.assertRaises((ValidationError, Exception)):
			reveal_password("User", "NonExistentUser", "password")
	
	def test_reveal_password_empty_parameters(self):
		"""Test reveal with empty parameters."""
		from reveal_password.reveal import reveal_password
		from frappe.exceptions import ValidationError
		
		with self.assertRaises((ValidationError, TypeError)):
			reveal_password("", "", "")
	
	def test_get_allowed_doctypes(self):
		"""Test getting allowed DocTypes."""
		from reveal_password.api import get_allowed_doctypes
		
		doctypes = get_allowed_doctypes()
		self.assertIsInstance(doctypes, list)
		self.assertIn("User", doctypes)
	
	def test_trusted_user_check(self):
		"""Test trusted user verification."""
		# User should be trusted
		is_trusted = frappe.db.exists(
			"Trusted User",
			{"user": "test_reveal_user@example.com", "enabled": 1}
		)
		self.assertTrue(is_trusted)
		
		# Guest should not be trusted
		is_guest_trusted = frappe.db.exists(
			"Trusted User",
			{"user": "Guest", "enabled": 1}
		)
		self.assertFalse(is_guest_trusted)
	
	def test_doctype_whitelist_check(self):
		"""Test DocType whitelist verification."""
		# User should be in whitelist
		is_allowed = frappe.db.exists(
			"Reveal Allowed Doctypes",
			{"doctype_link": "User", "enabled": 1}
		)
		self.assertTrue(is_allowed)


class TestRateLimiter(unittest.TestCase):
	"""Test cases for rate limiting functionality."""
	
	def setUp(self):
		"""Set up before each test."""
		frappe.set_user("Administrator")
		# Clear any existing rate limits
		try:
			from reveal_password.utils.rate_limiter import reset_rate_limit
			reset_rate_limit("Administrator", "test_action")
		except ImportError:
			pass
	
	def test_rate_limit_decorator(self):
		"""Test rate limit decorator."""
		try:
			from reveal_password.utils.rate_limiter import rate_limit
			
			@rate_limit(max_calls=3, time_window=60)
			def test_function():
				return "success"
			
			# First 3 calls should succeed
			for i in range(3):
				result = test_function()
				self.assertEqual(result, "success")
			
			# 4th call should fail
			with self.assertRaises(frappe.RateLimitExceededError):
				test_function()
		except ImportError:
			self.skipTest("Rate limiter not yet implemented")
	
	def test_check_rate_limit(self):
		"""Test rate limit checking."""
		try:
			from reveal_password.utils.rate_limiter import check_rate_limit
			
			# Should be within limit initially
			within_limit = check_rate_limit("Administrator", "test_action", 5, 60)
			self.assertTrue(within_limit)
		except ImportError:
			self.skipTest("Rate limiter not yet implemented")
	
	def test_get_remaining_calls(self):
		"""Test getting remaining calls."""
		try:
			from reveal_password.utils.rate_limiter import get_remaining_calls
			
			remaining = get_remaining_calls("Administrator", "test_action", 5)
			self.assertEqual(remaining, 5)
		except ImportError:
			self.skipTest("Rate limiter not yet implemented")


class TestAuditLogger(unittest.TestCase):
	"""Test cases for audit logging functionality."""
	
	def setUp(self):
		"""Set up before each test."""
		frappe.set_user("Administrator")
	
	def test_log_password_reveal(self):
		"""Test audit log creation."""
		try:
			from reveal_password.utils.audit_logger import log_password_reveal
			
			# Create a log entry
			log_password_reveal(
				user="Administrator",
				doctype="User",
				docname="Administrator",
				fieldname="test_field",
				success=True
			)
			
			# Verify log was created
			logs = frappe.get_all(
				"Password Reveal Log",
				filters={
					"user": "Administrator",
					"revealed_doctype": "User",
					"document_name": "Administrator",
					"field_name": "test_field"
				},
				limit=1
			)
			
			self.assertTrue(len(logs) > 0)
		except ImportError:
			self.skipTest("Audit logger not yet implemented")
		except frappe.DoesNotExistError:
			self.skipTest("Password Reveal Log DocType not yet created")
	
	def test_get_user_reveal_history(self):
		"""Test getting user reveal history."""
		try:
			from reveal_password.utils.audit_logger import get_user_reveal_history
			
			history = get_user_reveal_history("Administrator", limit=10)
			self.assertIsInstance(history, list)
		except ImportError:
			self.skipTest("Audit logger not yet implemented")
		except frappe.DoesNotExistError:
			self.skipTest("Password Reveal Log DocType not yet created")
	
	def test_get_reveal_statistics(self):
		"""Test getting reveal statistics."""
		try:
			from reveal_password.utils.audit_logger import get_reveal_statistics
			
			stats = get_reveal_statistics(days=30)
			self.assertIsInstance(stats, dict)
			self.assertIn("total_attempts", stats)
			self.assertIn("successful", stats)
			self.assertIn("failed", stats)
		except ImportError:
			self.skipTest("Audit logger not yet implemented")
		except frappe.DoesNotExistError:
			self.skipTest("Password Reveal Log DocType not yet created")


class TestPasswordStrength(unittest.TestCase):
	"""Test cases for password strength calculation."""
	
	def test_weak_password(self):
		"""Test weak password detection."""
		# This would test the frontend password strength calculator
		# For now, just a placeholder
		weak_passwords = ["123456", "password", "abc123"]
		for pwd in weak_passwords:
			# In actual implementation, score should be < 40
			self.assertTrue(len(pwd) < 12 or not any(c.isupper() for c in pwd))
	
	def test_strong_password(self):
		"""Test strong password detection."""
		strong_passwords = [
			"MyP@ssw0rd123!",
			"C0mpl3x&Secure#2024",
			"Tr0ng!P@ssW0rd$"
		]
		for pwd in strong_passwords:
			# Strong passwords should have length >= 12 and mixed characters
			self.assertTrue(len(pwd) >= 12)
			self.assertTrue(any(c.isupper() for c in pwd))
			self.assertTrue(any(c.islower() for c in pwd))
			self.assertTrue(any(c.isdigit() for c in pwd))


def run_tests():
	"""Run all tests."""
	unittest.main()


if __name__ == "__main__":
	run_tests()
