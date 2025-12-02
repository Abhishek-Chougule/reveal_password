# Copyright (c) 2025, Abhishek Chougule and contributors
# For license information, please see license.txt

import frappe
import subprocess
import sys
import os

def after_install():
	"""
	Run after the app is installed.
	Installs Python dependencies from requirements.txt.
	"""
	install_dependencies()

def before_install():
	install_dependencies()

def install_dependencies():
	"""
	Install dependencies from requirements.txt using pip.
	"""
	app_name = "reveal_password"
	app_path = frappe.get_app_path(app_name)
	requirements_path = os.path.join(os.path.dirname(app_path), "requirements.txt")

	if os.path.exists(requirements_path):
		print(f"Installing dependencies for {app_name}...")
		try:
			subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", requirements_path])
			print(f"Dependencies for {app_name} installed successfully.")
		except subprocess.CalledProcessError as e:
			frappe.throw(f"Failed to install dependencies: {str(e)}")
	else:
		print(f"requirements.txt not found at {requirements_path}")
