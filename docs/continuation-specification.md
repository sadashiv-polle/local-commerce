# CONTINUATION FUNCTIONALITY PROMPT

You are working inside an existing Frappe/ERPNext custom application repository.

The application structure has already been created. Do not recreate, rename, replace or reorganize the Frappe app.

## EXISTING APPLICATION IDENTITY

* App name: `local_commerce`
* Python package: `local_commerce`
* Frappe module: `Local Commerce`
* Custom DocType prefix: `LC`
* Backend: Frappe Framework v15
* ERP system: ERPNext v15
* Frontend: Vue 3
* Architecture: One Frappe app containing one unified Vue application

The project is a multi-shop local commerce, ordering, delivery, marketplace payment and ERPNext integration platform.

It must support different businesses, including:

* Fish shops
* Meat shops
* Grocery stores
* Restaurants
* Fast-food businesses
* Bakeries
* Pharmacies, where legally appropriate
* Local retailers
* Other small and medium businesses

The repository already contains partially completed work. Your responsibility is to inspect it carefully, understand what is already working and implement the remaining functionality.

Do not assume that a feature is missing merely because its filename differs from your preferred naming convention.

---

# 1. INSPECT THE EXISTING IMPLEMENTATION FIRST

Before modifying any code, inspect the complete repository.

Review:

* Existing DocTypes and their fields
* Child DocTypes
* DocType controllers
* Existing hooks
* Custom fields
* Fixtures
* Patches
* Roles and permissions
* Permission query conditions
* User permission logic
* API endpoints
* Service modules
* Background jobs
* Scheduler events
* Realtime events
* ERPNext integrations
* Vue pages
* Vue components
* Stores and composables
* Router configuration
* API client
* Authentication handling
* Dashboards
* Reports
* Tests
* Documentation
* Git status and existing uncommitted work

Also inspect the installed Frappe and ERPNext versions before using framework APIs.

Use repository search extensively. Trace every important feature from the frontend through the API and service layer to the DocType or ERPNext transaction.

Do not modify files until this inspection is complete.

---

# 2. CREATE A FUNCTIONAL GAP ANALYSIS

After inspection, create or update:

`IMPLEMENTATION_STATUS.md`

For every required feature, classify it as:

* Complete and verified
* Implemented but incomplete
* Implemented but broken
* Backend only
* Frontend only
* Missing
* Blocked by configuration or external credentials

The status document must contain:

| Module | Requirement | Existing implementation | Status | Missing work | Files involved | Test status |
| ------ | ----------- | ----------------------- | ------ | ------------ | -------------- | ----------- |

Do not mark anything complete simply because a DocType, page or API exists.

A feature is complete only when:

* Backend business logic works
* Server-side permissions are enforced
* Required UI works
* Validation and error handling exist
* Relevant tests pass
* The workflow works from beginning to end

After preparing the gap analysis, begin implementation. Do not stop after giving me only a plan.

---

# 3. PRESERVE EXISTING WORK

Follow these rules throughout development:

* Preserve working functionality.
* Do not recreate completed features.
* Do not overwrite user changes.
* Do not rename existing DocTypes or fields without a migration and a strong reason.
* Do not delete existing functionality merely because you would design it differently.
* Reuse existing services, utilities and components where practical.
* Refactor only where necessary for security, correctness or maintainability.
* Keep migrations backward-compatible.
* Make patches idempotent.
* Never edit Frappe or ERPNext core files.
* Never create a separate Node, Express, Django or FastAPI backend.
* Do not replace ERPNext accounting or inventory with custom parallel systems.
* Do not hard-code site names, domains, bench paths, companies, shops or credentials.

If the current implementation conflicts with a requirement, explain the conflict and implement the safest migration path.

---

# 4. CORE MULTI-SHOP FUNCTIONALITY

The application must support multiple independent shops inside one Frappe/ERPNext site.

Each shop should be connected to an ERPNext Company where appropriate.

A shop must support:

* Shop profile
* Company
* Business type
* Logo and branding
* Contact details
* Address and location
* Operating hours
* Holidays and closures
* Warehouses
* Products
* Prices
* Inventory
* Orders
* Customers
* Shop staff
* Delivery personnel
* Delivery settings
* Payment settings
* Tax settings
* Capabilities
* Reports
* Settlements

Every relevant custom record must have an authoritative shop or company relationship.

The server must determine the permitted shop/company from the authenticated user. Never trust a shop, company, customer or driver identifier sent by the frontend.

Cross-shop access must fail even if someone manipulates:

* URLs
* Filters
* query parameters
* API payloads
* request bodies
* resource names

Apply the same isolation to:

* APIs
* reports
* background jobs
* exports
* realtime events
* file access
* dashboards

---

# 5. ROLES AND PERMISSIONS

Support at least:

## Platform Administrator

Can manage platform-wide shops, authorized companies, configuration, commissions, providers, users, reports and audit information.

## Shop Owner

Can access only assigned shops and companies.

Can manage their products, pricing, stock, orders, customers, staff, drivers, deliveries, reports and settlements.

## Shop Staff

Can access only permitted shop operations according to assigned roles and permissions.

## Delivery Person

Can access only assigned deliveries and the minimum customer information required to complete them.

## Customer

Can access only:

* Their own profile
* Their own addresses
* Their own cart
* Their own orders
* Their own invoices
* Their own payment status
* Their own delivery tracking
* Their own refunds

Frontend route guards are for user experience only. All permissions must be enforced on the server.

---

# 6. SHOP CAPABILITIES AND CONFIGURATION

Do not hard-code features for every shop.

Implement a configuration-driven capability system so each shop can enable or disable features such as:

* Normal delivery
* Scheduled delivery
* Customer pickup
* Cash on delivery
* Online payment
* Weight-based products
* Delivery tracking
* Delivery batching
* Refunds
* Discounts
* Multiple warehouses
* Driver management
* Preparation time
* Delivery radius
* Tax-inclusive pricing
* Notifications

The backend must validate enabled capabilities. Hiding a button in Vue is not sufficient.

---

# 7. PRODUCT CATALOGUE

Reuse ERPNext wherever appropriate:

* Item
* Item Group
* Item Price
* Price List
* UOM
* Warehouse
* Batch
* Serial Number where applicable
* Pricing Rule
* Tax templates

The customer catalogue must support:

* Shop-specific availability
* Categories
* Product images
* Product description
* Selling price
* Tax display
* Stock availability
* Variants
* Units of measure
* Minimum quantity
* Maximum quantity
* Quantity increments
* Featured products
* Search
* Filters
* Sorting
* Pagination
* Out-of-stock handling
* Shop operating status

Support weight-based products such as fish, meat, vegetables and similar items.

Weight-based products must support configured units, increments, estimated amounts and final fulfilment quantities where required.

Never trust product prices, taxes, delivery charges, discounts or totals received from the frontend. Calculate authoritative totals on the server.

---

# 8. INVENTORY AND RESERVATIONS

ERPNext inventory must remain authoritative.

Implement:

* Warehouse-level stock checks
* Shop-to-warehouse mapping
* Available quantity calculation
* Inventory reservation during checkout
* Reservation expiry
* Reservation release after failure or cancellation
* Reservation conversion after successful order confirmation
* Prevention of overselling
* Safe handling of concurrent orders
* Stock reconciliation support
* Inventory movement history
* Low-stock information for shop users

Reservation operations must be transactional and idempotent.

---

# 9. CUSTOMER EXPERIENCE

The customer-facing application must provide:

* Shop discovery or direct shop access
* Product catalogue
* Product details
* Cart
* Address selection
* New address creation
* Serviceability check
* Delivery method selection
* Delivery slot selection
* Payment method selection
* Server-calculated order summary
* Checkout
* Payment status
* Order confirmation
* Order history
* Order details
* Cancellation request
* Refund status
* Delivery tracking
* Profile management

Customers must not be given Desk access unless explicitly required.

---

# 10. CUSTOMER ADDRESSES AND SERVICEABILITY

Support:

* Saved customer addresses
* Latitude and longitude
* Address labels
* Default address
* Delivery instructions
* Contact number
* Address validation
* Immutable order address snapshots

When an order is placed, store an address snapshot. Later edits to the customer’s saved address must not change historical orders.

Serviceability must support configurable:

* Delivery radius
* Postal code rules
* Geographic zones
* Distance provider
* Manual overrides
* Minimum order values
* Delivery restrictions

Distance and serviceability decisions must be calculated or verified by the server.

---

# 11. CART, CHECKOUT AND ORDER CREATION

The checkout workflow must:

1. Validate the authenticated customer.
2. Validate the selected shop.
3. Validate that the shop is open or can accept scheduled orders.
4. Validate shop capabilities.
5. Re-fetch products and prices from ERPNext.
6. Validate quantities and units.
7. Validate stock.
8. Validate the customer address.
9. Validate serviceability.
10. Validate the delivery method.
11. Validate slot capacity when scheduled delivery is selected.
12. Calculate discounts.
13. Calculate taxes.
14. Calculate delivery charges.
15. Calculate payment fees where legally permitted.
16. Calculate commission internally.
17. Calculate the final amount.
18. Reserve stock.
19. Create the required custom marketplace record.
20. Create the appropriate ERPNext Sales Order.
21. Start payment or confirm COD.
22. Return a safe checkout response.

The complete process must be protected against duplicate submissions.

Use an idempotency key for order creation.

---

# 12. ORDER STATE MACHINE

Implement a strict server-controlled order state machine.

Possible states may include:

* Draft
* Awaiting Payment
* Payment Pending
* Confirmed
* Accepted
* Preparing
* Ready for Pickup
* Awaiting Driver
* Assigned
* Out for Delivery
* Delivered
* Delivery Failed
* Cancellation Requested
* Cancelled
* Refund Pending
* Partially Refunded
* Refunded
* Closed

Define exactly which transitions are allowed and which roles can perform them.

Examples:

* Customers cannot mark an order Delivered.
* Drivers cannot change prices.
* Shop staff cannot mark an unpaid online order as paid.
* Delivered orders cannot silently return to Preparing.
* Cancellation after fulfilment must follow refund/return procedures.

Every transition must:

* Validate the current state
* Validate the requested next state
* Validate the authenticated role
* Record the timestamp
* Record the user
* Record the reason where required
* Add an audit entry
* Publish the appropriate realtime event
* Trigger configured notifications

---

# 13. NORMAL AND SCHEDULED DELIVERY

Support:

## Normal Delivery

* Immediate or next-available delivery
* Configurable preparation time
* Configurable delivery estimate
* Driver assignment
* Out-for-delivery workflow
* Delivery completion
* Failed delivery handling

## Scheduled Delivery

Separate:

* Booking window
* Order cutoff time
* Preparation window
* Actual delivery start time
* Estimated delivery window

Slots must be dynamically configured and must support:

* Shop
* Date
* Start and end time
* Booking cutoff
* Capacity
* Reserved capacity
* Delivery method
* Applicable zone
* Minimum order
* Maximum orders
* Enabled/disabled status

Do not hard-code delivery slot times in Vue or Python.

Prevent overbooking through transactional capacity checks.

---

# 14. DELIVERY BATCHING AND ROUTING

Scheduled orders may be grouped into delivery batches.

A batch should support:

* Shop
* Company
* Slot
* Date
* Assigned driver
* Vehicle or capacity details where enabled
* Orders
* Stop sequence
* Total quantity
* Total weight
* Total amount
* COD amount
* Route distance
* Estimated duration
* Batch status

Routing must use a provider abstraction.

Implement:

* Configurable map provider
* Geocoding
* Distance calculation
* Route calculation
* ETA calculation
* Provider timeout handling
* Retry handling
* Cached results where safe
* Manual fallback

Do not claim mathematically optimal routing unless an actual optimisation algorithm is implemented. A documented heuristic is acceptable.

---

# 15. DRIVER FUNCTIONALITY

Delivery personnel must be able to:

* Log in securely
* View assigned deliveries
* View current delivery batch
* View customer address and instructions
* Open navigation
* Update permitted delivery states
* Record pickup
* Mark out for delivery
* Mark delivered
* Record delivery time
* Record payment collection
* Report failed delivery
* Select or enter a failure reason
* Add delivery notes
* Upload permitted proof of delivery
* Work with a PWA-friendly interface where practical

Driver capacity may include:

* Maximum orders
* Maximum weight
* Maximum volume
* Vehicle type
* Working hours
* Availability

Location tracking must be privacy-aware. Do not retain precise driver location indefinitely without a configured reason and retention policy.

---

# 16. DELIVERY FAILURE AND PROOF

A failed delivery must require a reason.

Support configurable reasons such as:

* Customer unavailable
* Incorrect address
* Customer rejected order
* Payment not available
* Access problem
* Product issue
* Vehicle problem
* Other

Record:

* Driver
* Time
* Location where permitted
* Reason
* Notes
* Evidence where permitted
* Next action
* Reschedule or cancellation decision

Delivery proof may include OTP confirmation, signature, photograph or manual confirmation depending on shop configuration.

---

# 17. DELIVERY PRICING

Delivery pricing must be configuration-driven.

Support rules based on:

* Shop
* Zone
* Distance
* Postal code
* Order value
* Weight
* Delivery method
* Delivery slot
* Free-delivery threshold
* Minimum fee
* Maximum fee
* Surge or special period where legally appropriate

The backend must calculate and return the delivery charge.

---

# 18. PAYMENTS

Create a provider abstraction. Business logic must not depend directly on one payment gateway.

Support:

* Online payment
* Cash on delivery
* Provider order creation
* Customer payment initiation
* Secure callback handling
* Webhook verification
* Payment success
* Payment failure
* Payment expiry
* Reconciliation
* Refunds
* Partial refunds where supported
* Provider reference storage

Never store raw card data.

Credentials must use Frappe Password fields or site configuration and must never be returned to Vue.

The frontend return page is not authoritative. Verified provider webhooks or secure provider verification must establish final payment status.

---

# 19. WEBHOOKS AND IDEMPOTENCY

Payment webhooks must:

* Verify signatures
* Reject invalid requests
* Store the provider event ID
* Be idempotent
* Safely handle duplicate events
* Safely handle out-of-order events
* Record the raw payload securely with sensitive-data controls
* Link the event to the correct payment and order
* Perform transactional updates
* Trigger reconciliation when inconsistent

Do not create duplicate:

* Orders
* Payments
* Payment Entries
* Invoices
* Refunds
* Settlements

---

# 20. CASH ON DELIVERY

COD must support:

* Shop-level enablement
* Order-value limits
* Customer restrictions
* Driver cash collection
* Amount expected
* Amount collected
* Collection timestamp
* Driver acknowledgement
* Shop handover
* Short or excess collection reporting
* Reconciliation
* Audit history

COD collection is not complete merely because the order is marked Delivered.

---

# 21. COMMISSIONS AND FEES

Implement configurable platform commission rules.

Rules may depend on:

* Shop
* Business type
* Product category
* Delivery method
* Payment method
* Order amount
* Date range

Support:

* Percentage commission
* Fixed commission
* Mixed calculation
* Tax on commission
* Payment processing fees
* Delivery fees
* Refund adjustments

Store an immutable calculation snapshot on each financial transaction.

Historical orders must not change when commission rules are edited later.

---

# 22. REFUNDS AND CANCELLATIONS

Refunds must be separate auditable records.

Support:

* Full refund
* Partial refund
* Refund request
* Approval
* Rejection
* Provider refund
* Refund status tracking
* Failure and retry
* Inventory impact
* Commission reversal
* Settlement adjustment
* ERPNext accounting entries

Cancellation policies must be configurable by:

* Shop
* Order state
* Time before delivery
* Payment method
* Delivery method

Never treat a cancelled order as automatically refunded unless the refund actually succeeds or the payment was never captured.

---

# 23. SHOP SETTLEMENTS

Implement marketplace settlements between the platform and each shop.

A settlement should include:

* Shop
* Company
* Settlement period
* Included orders
* Gross sales
* Refunds
* Commission
* Commission tax
* Payment fees
* Delivery adjustments
* COD adjustments
* Previous adjustments
* Net payable
* Settlement status
* Provider or bank reference
* Payment date
* Reconciliation status

Settlement line items must be traceable to source transactions.

Finalized settlements must not be silently recalculated when current rules change.

---

# 24. ERPNEXT ACCOUNTING AND INVENTORY INTEGRATION

Reuse standard ERPNext documents wherever appropriate:

* Company
* Customer
* Supplier
* Item
* Item Group
* Item Price
* Price List
* Warehouse
* Sales Order
* Delivery Note
* Sales Invoice
* Payment Entry
* Journal Entry
* Stock Entry
* Stock Reconciliation
* Address
* Contact
* Pricing Rule
* Tax templates

Clearly define when each ERPNext document is created and submitted.

Maintain links between marketplace records and ERPNext documents.

Do not duplicate ERPNext ledgers in custom DocTypes.

Financial postings must respect:

* Company
* Currency
* Fiscal year
* Cost center
* Accounts
* Taxes
* Payment method
* Stock settings
* Rounding rules

---

# 25. TAXES, INVOICES AND RECEIPTS

Tax and GST behaviour must use ERPNext configuration where possible.

Support:

* Tax-inclusive and tax-exclusive prices
* Shop/company tax templates
* Product tax categories
* Delivery charge taxation
* Commission taxation
* Proper rounding
* Invoice generation
* Customer receipt
* Downloadable or printable receipt
* Shop branding
* Payment status
* Order and delivery information

Do not hard-code tax percentages.

---

# 26. REALTIME EVENTS AND NOTIFICATIONS

Use Frappe realtime functionality for events such as:

* New order
* Order accepted
* Order status changed
* Payment updated
* Driver assigned
* Delivery started
* Driver location updated where enabled
* Delivery completed
* Delivery failed
* Refund updated
* Settlement finalized

Never publish sensitive information on public or global channels.

Realtime subscriptions must be permission-aware and scoped to the relevant user, shop, order or driver.

Use provider abstractions for:

* Email
* SMS
* WhatsApp where configured
* Push notifications
* In-app notifications

Notification templates and triggers must be configurable.

---

# 27. BACKGROUND JOBS

Use Frappe background workers for:

* Payment verification
* Payment reconciliation
* Refund processing
* Settlement generation
* Notification delivery
* Route calculation
* Slot generation
* Reservation expiry
* Abandoned checkout cleanup
* Scheduled order preparation alerts
* Retryable provider operations
* Data-retention cleanup

Jobs must be:

* Idempotent
* Permission-aware
* Tenant-aware
* Retry-safe
* Observable
* Safe against duplicate execution

Do not put long-running provider calls inside normal web requests when a background job is more appropriate.

---

# 28. UNIFIED VUE APPLICATION

Keep one Vue application for all roles.

After authentication, determine:

* Logged-in user
* Roles
* Permissions
* Customer identity
* Assigned shops
* Assigned companies
* Enabled capabilities
* Feature flags

Then render the appropriate interface.

Required areas include:

## Platform Administration

* Shops
* Companies
* Users
* Capabilities
* Orders
* Deliveries
* Payments
* Refunds
* Commissions
* Settlements
* Provider configuration
* Reports
* Audit information

## Shop Owner and Staff

* Dashboard
* Orders
* Products
* Pricing
* Inventory
* Customers
* Drivers
* Delivery slots
* Delivery batches
* Delivery settings
* Payments
* Refunds
* Settlements
* Reports
* Shop settings

## Driver

* Assigned deliveries
* Batch details
* Navigation
* Delivery state updates
* Failed-delivery reporting
* COD collection
* Proof of delivery

## Customer

* Catalogue
* Product details
* Cart
* Addresses
* Checkout
* Payments
* Orders
* Tracking
* Cancellations
* Refunds
* Profile

The Vue interface must include:

* Loading states
* Empty states
* Error states
* Form validation
* Permission-aware navigation
* Responsive layouts
* Accessible controls
* Pagination
* Safe retry handling
* Prevention of duplicate form submissions

Business-critical validation must remain on the server.

---

# 29. REPORTING AND DASHBOARDS

Implement permission-aware reports for:

* Sales
* Orders
* Order status
* Products
* Inventory
* Low stock
* Customers
* Deliveries
* Delivery performance
* Failed deliveries
* Drivers
* COD collection
* Payments
* Payment failures
* Refunds
* Commission
* Settlements
* Tax summaries
* Shop performance

Reports must enforce shop/company isolation.

Use server-side filtering and pagination. Do not load complete tables into Vue merely to filter them in the browser.

Support controlled CSV or Excel export where appropriate.

---

# 30. SECURITY AND AUDIT

Implement:

* Server-side authorization
* Permission query conditions
* Document-level permission checks
* Tenant isolation
* CSRF protection
* Input validation
* Output filtering
* Rate limiting for sensitive APIs
* Secure file access
* Webhook signature verification
* Secret protection
* Duplicate request protection
* Safe error responses
* Audit logging
* Data-retention rules

Audit important events including:

* Order state changes
* Payment status changes
* Refund actions
* Settlement actions
* Price changes
* Inventory adjustments
* Delivery assignment
* COD handling
* Permission changes
* Provider configuration changes

Audit records must be append-only for normal users.

Never expose stack traces, SQL errors, secrets or internal provider responses to customers.

---

# 31. TRANSACTIONS AND CONCURRENCY

Use database transactions and locking where required.

Protect:

* Checkout
* Stock reservation
* Slot capacity
* Order creation
* Payment updates
* Refund creation
* Driver assignment
* COD collection
* Settlement finalization

Handle:

* Double-click checkout
* Duplicate API calls
* Duplicate webhooks
* Two customers buying the last stock
* Two users assigning the same driver
* Multiple workers processing the same payment
* Concurrent settlement generation

Do not rely only on frontend buttons being disabled.

---

# 32. HISTORICAL IMMUTABILITY

Store snapshots for values that must remain historically accurate:

* Product name
* Product rate
* Tax
* Discount
* Delivery charge
* Commission rule
* Commission amount
* Payment fee
* Customer delivery address
* Shop identity
* Slot details
* Cancellation policy
* Refund calculation

Later configuration changes must not silently modify completed historical transactions.

---

# 33. TESTING REQUIREMENTS

Add or complete tests for:

* Role permissions
* Cross-shop access denial
* Customer data isolation
* Catalogue access
* Server-side pricing
* Stock validation
* Inventory reservation
* Reservation expiry
* Concurrent checkout
* Order idempotency
* Order state transitions
* Delivery slot capacity
* Driver assignment
* Driver capacity
* Failed delivery
* COD collection
* Delivery pricing
* Payment initiation
* Webhook signature verification
* Duplicate webhook handling
* Out-of-order payment events
* Refunds
* Commission calculation
* Settlement calculation
* ERPNext document creation
* Accounting entries
* Realtime event authorization
* Background-job idempotency

Use realistic factories or test fixtures.

Do not write meaningless tests that only confirm a record can be inserted.

---

# 34. DEMO AND DEVELOPMENT DATA

Provide an optional, idempotent demo-data command that can create:

* Platform administrator
* Example companies
* Example shops
* Shop owners and staff
* Customers
* Drivers
* Warehouses
* Products
* Prices
* Stock
* Delivery zones
* Delivery slots
* Example orders
* Example payment states

Demo data must never run automatically in production.

Do not commit passwords or real credentials.

---

# 35. IMPLEMENTATION PRIORITY

Implement missing work in this order unless repository dependencies require a small adjustment:

1. Permissions and multi-shop isolation
2. Shop/company foundation
3. Products, pricing and inventory
4. Customer addresses and serviceability
5. Cart and server-authoritative checkout
6. Inventory reservation
7. Order state machine
8. Normal delivery
9. Scheduled delivery and slot capacity
10. Driver assignment and delivery workflows
11. Payment provider abstraction
12. Payment webhooks and reconciliation
13. COD collection
14. Refunds and cancellations
15. Commission and settlements
16. ERPNext accounting integration
17. Realtime events and notifications
18. Dashboards and reports
19. Security hardening
20. Tests, demo data and documentation

Finish and test one coherent vertical workflow before moving to the next one.

---

# 36. WORKING METHOD

For each implementation phase:

1. Inspect the relevant existing code.
2. Update `IMPLEMENTATION_STATUS.md`.
3. Identify what is complete and what is missing.
4. Reuse working components.
5. Implement the missing backend logic.
6. Add server-side permissions and validation.
7. Implement or connect the required Vue interface.
8. Add tests.
9. Run the relevant tests.
10. Run linting and frontend build checks.
11. Run migration if schema or fixtures changed.
12. Report the exact files changed.
13. Continue to the next incomplete feature.

Do not stop after every small file to ask for permission.

Ask me only when:

* A required business decision cannot be inferred from configuration
* External credentials are required
* A destructive migration is unavoidable
* Existing implementations conflict in a way that could cause data loss
* Multiple choices would materially change accounting or payment behaviour

Otherwise, make the safest configuration-driven decision and continue.

---

# 37. VERIFICATION

After relevant changes, run the applicable commands available in the environment, including:

```bash
bench --site <test-site> migrate
bench build --app local_commerce
bench --site <test-site> run-tests --app local_commerce
```

Also run the repository’s configured:

* Python formatter
* Python linter
* JavaScript/Vue linter
* Frontend unit tests
* Frontend production build

Fix failures caused by your changes.

Do not claim a test, build, migration or feature passed unless you actually ran it successfully.

If a command cannot run, state:

* The exact command
* Why it could not run
* What was verified instead
* What remains unverified

---

# 38. PROHIBITED SHORTCUTS

Do not:

* Rebuild the app scaffold
* Start a second app
* Create another backend
* Replace ERPNext accounting
* Replace ERPNext inventory
* Edit framework core files
* Trust prices from Vue
* Trust shop/company IDs from requests
* Use frontend-only permissions
* Hard-code delivery prices, commissions, taxes or slots
* Store raw card data
* Treat frontend payment redirects as payment confirmation
* Create duplicate records during retries
* Create essential production records manually without fixtures or migrations
* Leave incomplete `TODO` implementations
* Use pseudocode instead of working code
* Mark untested functionality as complete
* Remove existing functionality without proving it is obsolete
* Change historical financial records when configuration changes
* load entire datasets into the frontend for filtering

---

# 39. IMMEDIATE STARTING INSTRUCTION

Begin now by inspecting the current repository.

Then:

1. Summarize what has already been implemented.
2. Create or update `IMPLEMENTATION_STATUS.md`.
3. Identify the highest-priority incomplete end-to-end workflow.
4. Implement that workflow using the existing codebase.
5. Add or update tests.
6. Run the relevant verification commands.
7. Fix problems found during verification.
8. Continue with the next incomplete requirement.

The repository is the source of truth for current implementation status.

Do not recreate the project structure.

Do not give me only recommendations or a future plan. Work directly on the existing application and progressively complete the remaining functionality.
