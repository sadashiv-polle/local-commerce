# Implementation status

Repository inspected before this continuation. Baseline commit: 21de974. No
uncommitted changes at inspection. Local Python 3.13.5; Bench/Frappe/ERPNext not
installed locally. User server reports Frappe and ERPNext 15.109.0. No feature is
labelled complete without end-to-end Bench verification.

| Module | Requirement | Existing implementation | Status | Missing work | Files involved | Test status |
| --- | --- | --- | --- | --- | --- | --- |
| Identity | Login, CSRF, role-aware unified UI | Frappe session, Vue role routing | Implemented but incomplete | HTTP session/CSRF tests | services/session.py; frontend/src/App.vue | Client tests pass; HTTP unrun |
| Isolation | Shops, Company, membership | LC Shop, LC Shop Member; Item ownership hooks | Implemented but incomplete | Wider ERPNext report/file isolation; Bench verification | permissions/; hooks.py | Local policy tests; Bench tests unrun |
| Shop profile | Name, status, Company, description | Owner settings | Implemented but incomplete | Branding, contacts, address, business type | doctype/lc_shop/; services/shops.py | Bench tests unrun |
| Hours | Holidays, operating hours, closures | Manual status only | Implemented but incomplete | Hours and order acceptance checks | LC Shop.status | No end-to-end tests |
| Capabilities | Configured per-shop operations | Empty capabilities response | Missing | Full capability system | services/session.py | None |
| Products | Create own ERPNext Items | Scoped keyed creation, edit, search, categories, UOM | Implemented but incomplete | Images, variants, quantity limits; Bench verification | services/products.py; Products.vue | Default-filter tests pass; Bench tests unrun |
| Prices | Item Price, Price List | Dedicated shop price list; owner price editor and audit | Implemented but incomplete | Bench verification; scheduled/multi-UOM/tax pricing | services/owner.py; Products.vue | Integration tests added, unrun |
| Inventory | Warehouse mapping, stock additions/removals, history | Company-checked setup; Material Receipt/Issue; keyed audit and history | Implemented but incomplete | Bench posting/concurrency verification; batch/serial, multiwarehouse, reconciliation UI | services/owner.py; LC Stock Operation; Products.vue | Pure checks pass; 11 integration tests unrun |
| Availability | Sold out, archive, low stock | Manual sold-out flag, archive/restore, stock-aware status and thresholds | Implemented but incomplete | Browser and Bench verification; customer publication | owner_rules.py; Products.vue | Pure status tests pass |
| Reservations | Checkout holds, expiry, concurrency | None | Missing | Reservation service/jobs | Not yet implemented | None |
| Customer catalog | Discovery, search, product detail, prices | Opt-in shops and paginated priced products | Implemented but incomplete | Search, media, browser and Bench verification | Store.vue; CustomerShop.vue; services/orders.py | Build passes; integration unrun |
| Addresses | Customer-owned addresses and snapshots | None | Missing | Standard Address integration and snapshots | Not yet implemented | None |
| Serviceability | Radius, zones, postal codes | None | Missing | Configuration and server validation | Not yet implemented | None |
| Cart/checkout | Server totals, stock checks, idempotency | None | Missing | Complete checkout vertical workflow | Not yet implemented | None |
| Orders | State machine, Sales Order, history | Delivery request → owner accept/prepare/ready/cancel; ERP Sales Order | Implemented but incomplete | Dispatch, completion, paid checkout, Bench verification | services/orders.py; LC Order; Orders.vue | 7 pure tests pass; 5 integration tests unrun |
| Delivery | Normal, scheduled, slots and pricing | None | Missing | Configured rules, slot locking | Not yet implemented | None |
| Routing | Batches, provider abstraction, ETA | None | Missing | Adapter, heuristic, retries | Not yet implemented | None |
| Drivers | Assignments, capacity, GPS, proof, failures | Role/membership only | Implemented but incomplete | All delivery operations | LC Shop Member | Policy tests only |
| Payments | Provider abstraction and verified payment | None | Missing | Implementation and sandbox credentials | Not yet implemented | None |
| Webhooks | Signatures, event idempotency, reconciliation | None | Missing | Secure provider processing | Not yet implemented | None |
| COD | Collection, handover, discrepancies | None | Missing | Ledger/workflow and reconciliation | Not yet implemented | None |
| Commissions | Rules, fees, snapshots | None | Missing | Calculation and immutable records | Not yet implemented | None |
| Refunds | Cancellation, partial refunds, approval | None | Missing | Policy, provider and accounting | Not yet implemented | None |
| Settlements | Traceable net payable and reconciliation | None | Missing | Marketplace settlement workflow | Not yet implemented | None |
| Accounting/tax | Sales, invoices, taxes, payments | Standard ERPNext installed on server | Missing | Scoped marketplace postings and tests | ERPNext integration pending | None |
| Realtime | User/shop scoped events | None | Missing | Authorized publication/subscription tests | No registered channels | None |
| Notifications/jobs | Providers, retry, retention | None | Missing | Adapters, scheduler/worker jobs | No registered jobs | None |
| Staff | Configurable delegated operations | Read-only Staff policy | Implemented but incomplete | Owner staff administration and granular capabilities | permissions/policy.py | Local policy tests |
| Reports | Inventory, sales, customers, finance, export | None | Missing | Scoped aggregates, pagination, exports | Not yet implemented | None |
| Audit/security | Ownership, validation, Version | Partial Item and shop hooks | Implemented but incomplete | Broader audit, rate limits, retention and HTTP tests | hooks.py; services/ | Partial tests |
| Demo | Optional idempotent seed | Test factories only | Missing | Development-only demo command | tests/helpers.py | Bench tests unrun |
| Deployment | Portable app, migration, CI/build | Working scaffold and build | Implemented but incomplete | Fresh install/reinstall, restore and production verification | install.py; README.md; workflows/ | Local build/lint pass historically |

## Active vertical workflow

Owner products, prices, warehouse configuration, manual availability and audited
ERPNext stock adjustments. Preserve existing Items and balances. Do not use a
manual stock issue to represent a sale: sales need the future order/invoice flow.
The full owner module also depends on the missing order, customer, driver and
financial workflows above; this milestone must not be presented as all of them.

## This continuation — verification and changed files

Implemented the owner product/price/stock workflow, preserving existing scaffolding.
Local results: 22 Python unit tests and 5 frontend client tests passed; Ruff lint
and formatting, Vue lint, and Vite production build passed. No feature is promoted
to Complete and verified: database, browser, concurrency and accounting tests need
an actual Bench site.

Created: `services/owner.py`, `services/owner_rules.py`, `api/owner.py`, canonical
`doctype/lc_stock_operation/` JSON/controller/tests, `tests/test_owner_inventory.py`,
local `tests/test_owner_rules.py`, this gap analysis and `docs/owner-inventory.md`.
Updated: `services/products.py`, `api/products.py`, `hooks.py`, `install.py`, LC Shop
JSON, Vue Products/api/style files, frontend API tests, README/API/verification docs.
Paths for server modules above are under `local_commerce`; new Bench tests are
under `local_commerce/tests`. No source in Frappe/ERPNext was modified.

Next dependency: run the actual owner stock/pricing tests and resolve site
configuration failures before enabling checkout/reservations or implementing the
remaining owner order/customer/delivery/settlement workflows. Local verification
cannot certify financial postings or concurrent stock behavior.


## Delivery request milestone

Added an opt-in customer delivery catalogue, cart/address request and owner Orders
inbox, backed by draft/accepted ERPNext Sales Orders. See `docs/delivery-orders.md`
for setup and exact limitations. Postal-code matching, address snapshots, scoped
customer records, server prices and keyed retries implemented. This is not a paid
checkout: stock is checked/reserved at owner acceptance, not held during request.
No driver dispatch, payment, invoice, delivered state or expiry jobs are implemented.
Local verification: 29 Python tests, 5 frontend tests, Ruff, Vue lint and production
build pass. Five new Bench integration tests are added but unrun. No database or
browser verification claim is made. Delivery fee taxation remains incomplete.
