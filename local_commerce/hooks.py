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
before_migrate = "local_commerce.install.before_migrate"
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

permission_query_conditions["LC Stock Operation"] = "local_commerce.services.owner.operation_query"
has_permission["LC Stock Operation"] = "local_commerce.services.owner.operation_permission"
doc_events["LC Shop"] = {"validate": "local_commerce.services.owner.validate_configuration"}
for _doctype in (
    "Item Price",
    "Price List",
    "Warehouse",
    "Bin",
    "Stock Entry",
    "Stock Ledger Entry",
    "GL Entry",
):
    permission_query_conditions[_doctype] = "local_commerce.services.owner.restricted_query"
    has_permission[_doctype] = "local_commerce.services.owner.restricted_permission"
    doc_events[_doctype] = {
        "validate": "local_commerce.services.owner.restricted_write",
        "on_trash": "local_commerce.services.owner.restricted_write",
        "before_rename": "local_commerce.services.owner.restricted_write",
    }
doc_events["Stock Entry"]["before_cancel"] = "local_commerce.services.owner.immutable_stock_entry"

permission_query_conditions["LC Order"] = "local_commerce.services.orders.query"
has_permission["LC Order"] = "local_commerce.services.orders.permission"
doc_events["LC Shop"]["validate"] = [
    "local_commerce.services.owner.validate_configuration",
    "local_commerce.services.orders.validate_delivery",
]
for _doctype in (
    "Sales Order",
    "Delivery Note",
    "Sales Invoice",
    "Payment Entry",
    "Customer",
    "Address",
):
    permission_query_conditions[_doctype] = "local_commerce.services.owner.restricted_query"
    has_permission[_doctype] = "local_commerce.services.owner.restricted_permission"
    doc_events[_doctype] = {
        event: "local_commerce.services.owner.restricted_write"
        for event in ("validate", "on_trash", "before_rename")
    }
for _event in ("validate", "before_submit", "before_cancel", "on_trash"):
    doc_events["Sales Order"][_event] = [
        "local_commerce.services.owner.restricted_write",
        "local_commerce.services.orders.protect_sales_order",
    ]
    doc_events["Delivery Note"][_event] = [
        "local_commerce.services.owner.restricted_write",
        "local_commerce.services.orders.protect_delivery_note",
    ]
    doc_events["Sales Invoice"][_event] = [
        "local_commerce.services.owner.restricted_write",
        "local_commerce.services.orders.protect_payment_document",
    ]
    doc_events["Payment Entry"][_event] = [
        "local_commerce.services.owner.restricted_write",
        "local_commerce.services.orders.protect_payment_document",
    ]

permission_query_conditions["LC Customer Account"] = "local_commerce.services.customers.query"
has_permission["LC Customer Account"] = "local_commerce.services.customers.permission"
permission_query_conditions["LC Customer Address"] = (
    "local_commerce.services.customers.address_query"
)
has_permission["LC Customer Address"] = "local_commerce.services.customers.address_permission"

permission_query_conditions["LC COD Collection"] = "local_commerce.services.orders.collection_query"
has_permission["LC COD Collection"] = "local_commerce.services.orders.collection_permission"
