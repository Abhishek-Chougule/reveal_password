# Copyright (c) 2025, Abhishek Chougule and contributors
# For license information, please see license.txt

"""
Rate limiting utilities for password reveal operations.

This module provides decorators and utilities for implementing rate limiting
to prevent abuse and brute force attacks.
"""

import frappe
from frappe import _
from functools import wraps
import time
from typing import Callable, Any


def rate_limit(max_calls: int = 5, time_window: int = 60) -> Callable:
	"""
	Rate limiting decorator for API methods.
	
	Limits the number of times a function can be called by a user within
	a specified time window. Uses Redis for distributed rate limiting.
	
	Args:
		max_calls: Maximum number of calls allowed within the time window
		time_window: Time window in seconds
		
	Returns:
		Decorated function with rate limiting
		
	Example:
		@frappe.whitelist()
		@rate_limit(max_calls=5, time_window=60)
		def my_api_method():
			pass
			
	Raises:
		frappe.RateLimitExceededError: When rate limit is exceeded
	"""
	def decorator(func: Callable) -> Callable:
		@wraps(func)
		def wrapper(*args: Any, **kwargs: Any) -> Any:
			user = frappe.session.user
			key = f"rate_limit:{func.__name__}:{user}"
			
			try:
				# Get Redis connection (Frappe's cache)
				cache = frappe.cache()
				
				# Get current count
				current = cache.get(key)
				
				if current and int(current) >= max_calls:
					# Log rate limit violation
					frappe.log_error(
						f"Rate limit exceeded for user {user} on {func.__name__}",
						"Rate Limit Violation"
					)
					
					# Throw rate limit error
					frappe.throw(
						_("Too many requests. Please try again in {0} seconds.").format(
							cache.ttl(key) or time_window
						),
						frappe.RateLimitExceededError
					)
				
				# Increment counter
				pipe = cache.pipeline()
				pipe.incr(key)
				
				# Set expiry only if this is the first request
				if not current:
					pipe.expire(key, time_window)
				
				pipe.execute()
				
				# Execute the original function
				return func(*args, **kwargs)
				
			except frappe.RateLimitExceededError:
				raise
			except Exception as e:
				# If rate limiting fails, log error but allow request
				# (fail open for availability)
				frappe.log_error(
					f"Rate limiting error: {str(e)}",
					"Rate Limiter Error"
				)
				return func(*args, **kwargs)
				
		return wrapper
	return decorator


def check_rate_limit(user: str, action: str, max_calls: int = 5, time_window: int = 60) -> bool:
	"""
	Check if a user has exceeded the rate limit for a specific action.
	
	Args:
		user: User identifier
		action: Action name
		max_calls: Maximum calls allowed
		time_window: Time window in seconds
		
	Returns:
		True if within rate limit, False if exceeded
	"""
	try:
		cache = frappe.cache()
		key = f"rate_limit:{action}:{user}"
		current = cache.get(key)
		
		return not current or int(current) < max_calls
	except Exception as e:
		frappe.log_error(f"Error checking rate limit: {str(e)}", "Rate Limiter Error")
		return True  # Fail open


def reset_rate_limit(user: str, action: str) -> None:
	"""
	Reset the rate limit counter for a user and action.
	
	Args:
		user: User identifier
		action: Action name
	"""
	try:
		cache = frappe.cache()
		key = f"rate_limit:{action}:{user}"
		cache.delete(key)
	except Exception as e:
		frappe.log_error(f"Error resetting rate limit: {str(e)}", "Rate Limiter Error")


def get_remaining_calls(user: str, action: str, max_calls: int = 5) -> int:
	"""
	Get the number of remaining calls for a user and action.
	
	Args:
		user: User identifier
		action: Action name
		max_calls: Maximum calls allowed
		
	Returns:
		Number of remaining calls
	"""
	try:
		cache = frappe.cache()
		key = f"rate_limit:{action}:{user}"
		current = cache.get(key)
		
		if not current:
			return max_calls
			
		remaining = max_calls - int(current)
		return max(0, remaining)
	except Exception as e:
		frappe.log_error(f"Error getting remaining calls: {str(e)}", "Rate Limiter Error")
		return max_calls  # Fail open


def get_time_until_reset(user: str, action: str) -> int:
	"""
	Get the time in seconds until the rate limit resets.
	
	Args:
		user: User identifier
		action: Action name
		
	Returns:
		Seconds until reset, or 0 if no limit is active
	"""
	try:
		cache = frappe.cache()
		key = f"rate_limit:{action}:{user}"
		ttl = cache.ttl(key)
		
		return ttl if ttl and ttl > 0 else 0
	except Exception as e:
		frappe.log_error(f"Error getting TTL: {str(e)}", "Rate Limiter Error")
		return 0
