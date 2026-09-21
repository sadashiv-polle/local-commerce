from frappe.model.document import Document

from local_commerce.services.scheduled import validate_slot


class LCDeliverySlot(Document):
    def validate(self):
        validate_slot(self)
