# Store category menu

Configure in the Vue app at Shop workspace → Storefront settings → Category menu. Only LC Platform Administrators (and Administrator) can read/change menu settings or upload category artwork. Customers and guests receive only shown categories.

Use the global switch to show/hide the whole menu. Individual checkboxes control each tile. Select an Item Group to add a tile, edit its customer label and section heading, upload JPG/PNG/WebP artwork (maximum 5 MB), and use the arrows to reorder tiles. Save category menu to publish changes. Categories with the same heading share a section and top section tab. Each Item Group appears once; up to 40 tiles are supported.

The initial menu is seeded once during installation/migration with the commerce starter groups. Later migrations preserve hidden switches, removed categories, and empty menus. Public item images are used as fallback artwork when no category image is supplied. Otherwise a category icon is shown.

Tapping a tile filters public product search across active shops by its exact ERPNext Item Group; current prices, stock, and saved-address serviceability are returned. Search text further filters the selected category. Clear category to return to ordinary product search. Hiding a category changes navigation, not whether its products can be searched or ordered.

Deploy with git pull, bench --site mysite migrate, yarn build, cache clearing, and restart only frappe-benchs-web:. Integration checks on a disposable ERPNext site: bench --site TEST_SITE run-tests --app local_commerce --module local_commerce.tests.test_category_menu.
