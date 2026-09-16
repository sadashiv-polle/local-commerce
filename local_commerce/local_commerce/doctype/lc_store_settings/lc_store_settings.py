from frappe.model.document import Document

from local_commerce.permissions.scope import require_platform
from local_commerce.services.storefront import validate_settings


class LCStoreSettings(Document):
    def validate(self):
        require_platform()
        validate_settings(self)
        from local_commerce.services.category_menu import validate_menu

        validate_menu(self)
