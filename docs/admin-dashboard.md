# Master administration dashboard

Open `/local-commerce#/admin`. Platform administrators now land here after signing in. Owners continue to open `/shop`, riders `/delivery`, and customers `/store`. The dashboard is also linked from the existing admin workspace tabs and customer-facing header for administrators.

Only Administrator or an LC Platform Administrator can access its APIs. Guests, owners, staff, riders, and customers cannot read platform-wide records or perform dashboard mutations through these APIs.

## Overview

The overview shows today's placed orders, active shops, connected delivery partners, customer login accounts, enabled products, all outstanding order stages, and seven days of completed deliveries. Delivered sales are Sales Order totals for orders completed on the site date; they are not cash receipts or profit. Cash awaiting handover comes from LC COD Collections. Financial amounts are grouped by currency and never added across currencies. The visible overview refreshes every 30 seconds; other record pages refresh on demand.

## Manage operations

- Shops: search/filter shops, pause/resume accepting new orders without changing the weekly schedule, create a Draft shop with a new Company or explicitly link an unused existing Company, and open its workspace/setup.
- Orders: platform-wide searchable, paginated order register. Select a shop or Manage on a record to accept/cancel orders, prepare them, assign riders, and follow delivery using the existing authorized order controls.
- Inventory: platform-wide product register with live available stock and sold-out/low-stock states. Select a shop to create/edit products, upload images, change prices, and add/remove stock through existing stock operations.
- Team & riders: search/filter memberships, create memberships for existing enabled users, and edit role/enabled state. Matching LC roles are assigned by the existing membership controller. Multiple shops can be assigned to one rider. User account creation/editing stays in ERPNext's User record.
- Customers: view app-linked customer accounts and open the corresponding Customer records in ERPNext.
- Payments: review COD collections across shops and select a shop to reconcile cash handovers with the existing confirmation flow.
- Storefront: category visibility/artwork/ordering and reusable featured product lists inside the dashboard.
- Settings: direct links to companies, accounts, cost centers, tax templates, warehouses, Item Groups, price lists, users, email accounts, website settings, and notification records. Advanced ERP configuration continues to use its original forms.

Lists fetch at most 20 records plus a next-page marker. Inventory balance queries run only for the visible page. The shop selector loads the first 500 shops; records for other shops can still be opened through the paginated shop list or Manage actions.

## Validation

Local checks: `npm run lint`, `npm test`, `npm run build`, `.venv/bin/ruff check local_commerce tests`, and `.venv/bin/python -m unittest discover -s tests`.

Integration checks require a disposable ERPNext v15 test site: `bench --site TEST_SITE run-tests --app local_commerce --module local_commerce.tests.test_admin_dashboard`. These cover owner/guest access denial, live inventory and pagination, schedule-preserving pause, membership role assignment, and shop/company creation. A phone/laptop browser review remains necessary after deployment.
