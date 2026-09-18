# Local Commerce workspace

After installing the app or running `bench --site mysite migrate`, reload Frappe
Desk and open **Local Commerce** in the workspace sidebar, or visit
`/app/local-commerce`.

The top shortcuts open Shop workspace, Public storefront, Deliveries, Admin
dashboard and Storefront settings. Choose a shop in Shop workspace to manage its
products, stock, fish expiry, market prices and reports.

Record cards group shops and people, orders and payments, products and stock,
fish records, storefront settings, and Company accounts. All document permissions
and shop restrictions still apply. Admin app pages require platform administrator
access. Website Users need the Vue app; a workspace does not grant Desk access.

The workspace is visible to LC Platform Administrator, LC Shop Owner, LC Shop
Staff and LC Delivery Person roles with Desk access, and Administrator. Fish lots,
movements and price records are audit records; use the shop app to post changes.

Workspace definitions ship with the app and synchronize during migration. No
frontend rebuild is required for this workspace-only change.
