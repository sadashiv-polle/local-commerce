# Accounting reconciliation

This change uses existing LC Orders, invoices, Payment Entries and Journal Entries.
It adds backend-only reconciliation references to LC Order and administrator-only
settlement account settings to LC Shop. There is no second sales ledger.

## Cashfree refunds

Refund initiation remains in Cashfree. Only a refund fetched from Cashfree with
SUCCESS status, matching order, payment, currency and amount is booked.

- A full refund of a posted invoice creates a native credit note and an outgoing
  Payment Entry. The credit note has its own outstanding balance and does not
  return physical stock. Actual inventory returns must be recorded separately.
- A partial refund cannot identify the returned items or taxes from its cash amount.
  In **Platform → Cashfree → Recent payments**, choose **Prepare partial refund
  credit note**, open the draft in ERPNext, select the correct items/charges and
  submit it. Open **Refunds & accounting entries**, link that credit note to the
  provider refund ID and select **Retry verification**. The app posts the outgoing
  payment only when the original invoice, customer, company, currency, total and
  outstanding credit all match. Existing manually created credits can be linked.
- A full direct-merchant refund before an invoice was ever created records the
  receipt and refund through offsetting customer/clearing journals, without
  inventing a sale. An unbilled partial refund or an unbilled commissioned payment
  remains in review rather than guessing the accounting allocation.
- Easy Split commission reversal uses the actual vendor debit in `refund_splits`;
  missing or excessive split evidence stops posting. It never assumes commission
  was returned merely because the customer received a refund.
- Provider event IDs and native document references are stored atomically on the
  order. Replays reuse the entries. Cancelled linked entries require review.
- Refunded orders remain blocked from further fulfilment, including partial refunds;
  completing the financial entries is not authorization to deliver refunded goods.

## Cashfree bank settlements

In the administrator's Cashfree shop settings, select:

1. A dedicated Cashfree clearing ledger (Bank type).
2. A separate actual receiving bank ledger in the same Company and INR.
3. Gateway fee and gateway fee tax **expense** ledgers.
4. Optionally **Automatically reconcile paid orders and bank settlements every hour**.

The hourly job rotates through up to 20 eligible paid/refunded orders, including
already-delivered orders. **Reconcile bank settlement** also runs on demand.
Checkout and payment verification continue using API v2025-01-01; settlement
lookups use the documented v2026-01-01 response contract.

Direct merchant postings use the order's settlement allocation, not the entire
batch. Easy Split postings use only the configured vendor's completed credit
allocation. Bank debit + fee debit + fee-tax debit must equal clearing credit.
Native journals carry the bank UTR, provider processing date and order reference.
Posting date is the current accounting date; closed periods are not bypassed.

Fee tax is expensed. The app does not claim input tax credit without a tax invoice.
Postpaid/customer-paid fees, paginated or ambiguous vendor results, unexplained
adjustments and changed settlement evidence remain in review. Bank statement
matching still uses ERPNext Bank Reconciliation; the app does not have bank-feed access.

Before enabling automation for an existing shop, review old manual settlement
journals. A matching UTR on a manually created bank journal stops automatic posting.
The app does not silently reverse historical entries or fabricate adjustment amounts.

Provider contracts:
- https://www.cashfree.com/docs/api-reference/payments/latest/settlements/get-settlements-by-order-id
- https://www.cashfree.com/docs/api-reference/payments/latest/easy-split/get-split-and-settlement-details-by-orderid-v20

## Sales and profit reports

Fish reports include submitted online and offline Sales Invoices and credit notes
for the shop's products, Company and warehouse. Consolidated POS invoices appear
once they are posted as Sales Invoices; unconsolidated POS drafts are not ledger sales.

Cost comes from native Stock Ledger Entries for the invoice itself or its linked
Delivery Note, allocated to invoiced quantities. Missing stock cost is not zero:
profit displays **Awaiting stock cost** until valuation is available. Zero-cost
stock with a real stock ledger movement remains valid.

A financial credit reduces revenue only; an actual stock return also reverses
cost. Revenue follows invoice dates; stock quantities follow stock posting dates.
A later delivery can complete cost for an earlier invoice period. This operational
product-margin report is not the Company's net-profit statement: operating costs,
gateway fees and cash differences remain in ERPNext's Profit and Loss report.
Mixed-shop invoice delivery fees are excluded rather than attributed twice.

## COD differences

Handover creates the receipt only for cash actually collected. If an invoice remains
unpaid or cash remains unallocated, the collection stays **Difference Pending** and
the order shows **Partially Paid** or **Overpaid**. The rider's handover is recorded;
these amounts are not counted again as cash still due from the rider.

An administrator records the actual additional payment, an explicitly approved
write-off, or resolves the customer credit through native ERPNext accounting.
Then **Check balance again** moves the collection to Reconciled only when both
balances are cleared. Rechecking never creates another receipt. No shortage is
automatically written off and no excess cash is automatically called revenue.

Migration reclassifies previously Reconciled COD orders with outstanding invoices
or unallocated receipts. It does not change historical financial entries.

## Deployment and verification

After updating the repository, build and migrate:

```sh
cd ~/frappe-benchs/apps/local_commerce
npm ci
npm run build
cd ~/frappe-benchs
bench --site mysite migrate
bench --site mysite clear-cache
bench restart
```

Run native GL integration tests on a **disposable test site**, not the shop's live
site (the fixtures create Companies, accounts and orders):

```sh
bench --site TEST_SITE run-tests --app local_commerce --module local_commerce.tests.test_payment_accounting
bench --site TEST_SITE run-tests --app local_commerce --module local_commerce.tests.test_orders
bench --site TEST_SITE run-tests --app local_commerce --module local_commerce.tests.test_manual_upi
```

Local tests cover provider evidence, refund replay, credit matching, balanced
settlement journals, COD retries and historical migration, and relational report
fixtures. They do not replace native ERPNext tests or a real Cashfree sandbox cycle.
