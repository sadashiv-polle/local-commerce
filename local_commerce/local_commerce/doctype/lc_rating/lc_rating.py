import hashlib

from frappe.model.document import Document


class LCRating(Document):
    def autoname(self):
        self.name = hashlib.sha256(f"{self.customer}:{self.order}".encode()).hexdigest()
