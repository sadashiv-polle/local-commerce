from frappe.model.document import Document

from local_commerce.permissions.scope import require_platform
from local_commerce.services.storefront import validate_settings


class LCStoreSettings(Document):
    def validate(self):
        require_platform()
        from local_commerce.services.business_structure import validate_platform_change
        validate_platform_change(self)
        validate_settings(self)
        from local_commerce.services.category_menu import validate_menu

        validate_menu(self)

        from local_commerce.services.promotions import validate

        validate(self)
