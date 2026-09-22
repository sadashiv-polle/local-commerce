from frappe.model.document import Document

from local_commerce.services.recurring_delivery import sync_schedule, validate_schedule


class LCDeliverySchedule(Document):
    def validate(self):
        validate_schedule(self)

    def on_update(self):
        sync_schedule(self)

    def on_trash(self):
        from local_commerce.services.recurring_delivery import cleanup_schedule

        cleanup_schedule(self)
