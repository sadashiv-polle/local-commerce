import hashlib

import frappe
from frappe.model.document import Document


class LCFavourite(Document):
    def autoname(self):
        self.name = hashlib.sha256(f"{self.user}:{self.item}".encode()).hexdigest()

    def validate(self):
        if frappe.session.user == "Guest" or self.user != frappe.session.user:
            frappe.throw("Favourite access denied", frappe.PermissionError)
