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
    "LC Shop": "local_commerce.permissions.scope.shop_query",
    "LC Shop Member": "local_commerce.permissions.scope.member_query",
}
has_permission = {
    "LC Shop": "local_commerce.permissions.scope.shop_permission",
    "LC Shop Member": "local_commerce.permissions.scope.member_permission",
}
