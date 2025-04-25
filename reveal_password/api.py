import frappe

@frappe.whitelist()
def get_allowed_doctypes():
    return [d.doctype_link for d in frappe.get_all("Reveal Allowed Doctypes", filters={"enabled": 1}, fields=["doctype_link"])]

