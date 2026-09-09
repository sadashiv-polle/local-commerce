# Delivery requests and owner inbox

This milestone connects authenticated LC Customers to shop owners using ERPNext
Sales Orders. It is an order-request workflow, not a completed paid checkout or
last-mile delivery system. Default installation leaves delivery requests disabled.

## Configure a shop

Complete Inventory setup first. In LC Shop, set Active, configure exact postal
codes (one per line), and select a company-specific Sales Taxes and Charges
Template. Set a delivery fee and same-company account if needed, then enable
Delivery Requests. Configure Customer Group and Territory defaults in Selling
Settings. Assign LC Customer to customer users. Platform administrators can test
customer flows too; owner-only users need LC Customer for customer ordering.

The configured tax template is copied to each Sales Order. The delivery fee is an
additional Actual charge, appended after template taxes; this milestone does not
calculate tax on that delivery charge. Configure zero delivery fee for cases where
separate delivery taxation is required until that feature is implemented. No tax
rates are hard-coded. Test the shop's tax configuration before accepting orders.

## Use

Customers open `/local-commerce#/store`, select a shop, add products, provide the
recipient, phone, street, city and postal code, and send a delivery request. The
UI identifies prices as estimates until ERPNext calculates the saved request.
A company-scoped Customer and a standard shipping Address are created internally;
LC Order preserves the address snapshot. The browser stores an unconfirmed request
in sessionStorage for retry with the same idempotency key. This contains delivery
address data and is removed after success or a definitive validation rejection.

Owners open their shop workspace → Orders. Refresh retrieves current requests.
Requested → Accepted → Preparing → Ready. Ready means waiting for dispatch; it
does not represent delivery. Owners can cancel with a reason. Customers can cancel
only Requested orders. Staff can view but cannot transition orders. There is no
payment collection, paid status, delivery assignment, invoice or delivered action.

Requests create draft Sales Orders without reserving stock. Acceptance locks the
shop and stock rows, checks availability again, and submits the Sales Order using
normal ERPNext validation and reservation updates. Requested orders can therefore
compete for stock; a later acceptance is rejected when stock is insufficient.
Cancellation of an accepted order uses ERPNext cancellation; submitted dependent
records can prevent cancellation. Cancelled draft requests retain their draft SO
for audit and cannot be reopened through this workflow.

This is not an expiring checkout hold or an ERPNext Stock Reservation Entry
implementation. Other ERP entry points are not coordinated by the app shop lock;
concurrency against external ERP transactions remains a verification requirement.
ERP users must not fulfil these orders until the invoice/delivery workflow exists.

Each mutation is a single Frappe request transaction. No service commits. Request
keys are bound to user, shop, cart and address. Status transitions record Version
and comments. Scoped APIs expose a filtered response rather than raw Customer,
Address or Sales Order documents. Normal LC users cannot mutate orders through
resource APIs. Direct ERP report/custom SQL access still requires separate review.

## Verification

Standalone rules cover cart validation, invalid quantities, state transitions,
customer cancellation limits, required addresses and whole UOM quantities.
`local_commerce.tests.test_orders` adds five ERP integration cases for pricing,
replay, actual Sales Order submission/cancellation, stock rechecks, customer
isolation, postal validation and raw mutation denial. These require a disposable
ERPNext site and have not run in the local workspace:

```bash
bench --site TEST_SITE migrate
bench --site TEST_SITE run-tests --module local_commerce.tests.test_orders
```

Also manually test LC Customer login → delivery request → owner acceptance →
customer status refresh on desktop and mobile. Multi-session checkout, taxes,
rollback, address permissions and cancellation must be verified before live use.
