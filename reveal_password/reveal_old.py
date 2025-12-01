import frappe
from frappe.utils.password import get_decrypted_password
from frappe.exceptions import PermissionError

@frappe.whitelist()
def reveal_password(doctype, docname, fieldname):
    user = frappe.session.user
    if not frappe.db.exists("Trusted User", {"user": user, "enabled": 1}):
        raise PermissionError("You are not authorized to reveal passwords.")

    encrypted = frappe.db.get_value(doctype, docname, fieldname)
    if not encrypted:
        return ""

    return get_decrypted_password(doctype, docname, fieldname, raise_exception=False)
