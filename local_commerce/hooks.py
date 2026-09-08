app_name = "local_commerce"
app_title = "Local Commerce"
app_publisher = "Local Commerce Contributors"
app_description = "Multi-shop commerce for ERPNext"
app_email = "maintainers@example.invalid"
app_license = "MIT"
required_apps = ["erpnext"]

before_install = "local_commerce.install.before_install"
after_install = "local_commerce.install.after_install"
after_migrate = "local_commerce.install.after_migrate"
fixtures = [
    {
        "dt": "Role",
        "filters": [
            [
                "name",
                "in",
                [
                    "LC Platform Administrator",
                    "LC Shop Owner",
                    "LC Shop Staff",
                    "LC Delivery Person",
                    "LC Customer",
                ],
            ]
        ],
    }
]
permission_query_conditions = {
    "Item": "local_commerce.services.products.item_query",
    "LC Shop": "local_commerce.permissions.scope.shop_query",
    "LC Shop Member": "local_commerce.permissions.scope.member_query",
}
has_permission = {
    "Item": "local_commerce.services.products.item_permission",
    "LC Shop": "local_commerce.permissions.scope.shop_permission",
    "LC Shop Member": "local_commerce.permissions.scope.member_permission",
}

doc_events = {
    "Item": {
        "before_validate": "local_commerce.services.products.scope_creation_defaults",
        "validate": "local_commerce.services.products.validate_item",
        "on_trash": "local_commerce.services.products.protect_item",
        "before_rename": "local_commerce.services.products.protect_item",
    }
}
