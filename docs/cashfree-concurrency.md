# Cashfree checkout concurrency

Checkout session creation, payment verification and cancellation preflight contact
Cashfree before taking the shop inventory lock. A slow provider response therefore
does not hold that lock while other customers place orders for the same shop.
Stock checks and accounting still use the existing shop → order lock sequence.
COD and Manual UPI do not use the new payment guard.

## Transaction contract

`cashfree.begin_operation` is a standalone request/job boundary. Call it only
after read-only authorization checks and before inventory locks. It refuses to
commit pending database writes. It ends the initial read transaction so a
MariaDB repeatable-read snapshot cannot conceal a concurrent cancellation.

A site-and-order-specific MariaDB advisory lock then protects checkout,
verification and cancellation through the final transaction commit or rollback.
Different orders have different locks. A concurrent action for the same order
returns a retry message immediately; it does not wait while holding stock locks.
The connection also releases its advisory locks if the worker disconnects.
Accounting savepoint rollback deliberately retains the payment guard until the
outer transaction finishes. Do not call these services from inside a transaction
which already modified another document; commit that work at its own boundary.

Verification fetches remote order, payment and refund evidence first, then reads
the LC Order for update and records the result. Existing payment-reference checks
and receipt checks prevent duplicate accounting. Recorded refunds never decrease
because of a later incomplete provider response. Cancellation rechecks unpaid
state and the original payment snapshot under the normal inventory locks.

The reconciliation job commits verification before starting cancellation, so its
second network request cannot inherit accounting locks from verification.

Reference behavior: [MariaDB advisory locks](https://mariadb.com/docs/server/reference/sql-functions/secondary-functions/miscellaneous-functions/get_lock)
and [Frappe v15 transaction callbacks](https://docs.frappe.io/framework/user/en/api/database#database-transaction-hooks).

## Validation

Run `.venv/bin/python -m unittest discover -s tests`. Regression tests cover HTTP
before inventory locks, provider failures, concurrent guards for different/same
orders, commit/rollback release, cancellation revalidation, duplicate receipts,
late failures and refunds. These tests mock Frappe/provider connections; they do
not establish production throughput.

Before claiming capacity for 100 simultaneous customers, test a separate Bench
site with Cashfree Sandbox credentials and representative stock:

1. Start checkout for two different orders from the same shop. Delay one sandbox
   HTTP request using a test proxy and verify the other order can still be placed.
2. Start checkout and cancellation for the same order simultaneously. Expect one
   operation to retry. A cancelled order must not receive a new payment session.
3. Verify one successful sandbox payment concurrently from the return page and
   webhook. Expect one Sales Invoice and one Payment Entry after retries.
4. Simulate a provider timeout, then retry; the same gateway order ID must be
   reused. Test a missed webhook with the reconciliation job too.
5. Check expiry/cancellation releases stock, refunds stay blocked for review,
   and the existing COD and Manual UPI flows still complete.

Use increasing concurrency on that test site and record latency, errors, CPU,
memory, worker queue depth and DB lock waits. External calls still occupy web
workers; removing the inventory-lock bottleneck is not a server-capacity guarantee.
