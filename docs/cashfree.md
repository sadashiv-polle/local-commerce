# Cashfree payments and Easy Split

Cashfree is an optional third checkout method. Existing Cash on Delivery and Manual UPI
settings and workflows remain available. Cashfree is disabled until configured per shop.

## Installation

Deploy the application code, then run from the bench directory:

```sh
bench --site mysite backup
bench --site mysite migrate
bench build --app local_commerce
bench --site mysite clear-cache
bench --site mysite enable-scheduler
bench restart
```

Use your usual frontend build (`npm ci` followed by `npm run build` in the app directory)
if your deployment does not already run it. Refresh the installed app after deployment.
Keep the scheduler and workers running for missed-webhook recovery.

## Admin setup

Open the Local Commerce **Platform administration → Cashfree** section as an
LC Platform Administrator (or Administrator).

For an owned shop such as Fish World, choose **Receive payments into → Main merchant
account — my own shop**. Select your gateway profile, clearing account and Mode of Payment,
then enable and save. No Easy Split vendor, commission or commission expense account is
required. The gateway request omits splits and the payment uses the merchant account for
that profile. Normal Cashfree fees still apply in production. Sandbox does not move money.
Existing shops retain Easy Split until explicitly changed; existing orders always retain
the mode and amounts saved at checkout. The vendor setup below only applies to Easy Split.

1. Create a **Sandbox** gateway profile with the Client ID and Client Secret from Cashfree.
   Sandbox simulates gateway payments, but successful tests still create real ERP documents
   in the connected Frappe site. Use a separate test site and test Company.
2. Enable Easy Split in your Cashfree account and complete vendor onboarding there.
   Enter each existing shop's approved Cashfree vendor ID; this app does not duplicate
   Customer, Shop or vendor bank/KYC records.
3. For each shop, select the gateway profile, commission type (percentage or fixed INR),
   commission amount, and a Bank-type Mode of Payment.
4. Select an INR **Bank-type Asset account** in the shop's Company as the Cashfree clearing
   account, and an INR Expense account for marketplace commission. Create these in ERPNext
   if needed. The clearing account represents money due from the gateway, not bank cash.
5. Enable Cashfree for the shop and save. COD and Manual UPI can stay enabled independently.
6. Register the webhook URL shown in the panel in Cashfree for payment and refund events.
   The endpoint verifies Cashfree's raw-body signature using that profile's API secret.
   Do not disable CSRF globally. Production requires a public HTTPS site URL and Cashfree's
   required checkout-domain approval.

Create a separate Production profile with production credentials when ready. A profile's
environment and merchant Client ID cannot be changed after creation because historical
orders reference them. You can update its secret and enabled switch. Keep old credentials
usable until outstanding payments and refunds have been resolved. Secrets are encrypted
in Frappe Password storage; the settings API never returns them to Vue.

## Order and accounting behavior

- The backend creates the payment session using the saved Sales Order amount and currency.
  Browser checkout results alone never mark an order Paid.
- Cashfree must report both a paid order and a matching successful payment. Only then is
  the existing Sales Order submitted and the order automatically Accepted. There is no
  separate shop acceptance step for Cashfree orders.
- The app posts the Sales Invoice and Payment Entry against the clearing account. A
  commission Journal Entry debits commission expense and credits the clearing account.
  The shop receives its configured share through Easy Split; the remainder is the
  marketplace commission. Commission applies to the full total, including tax and delivery.
- Order totals, vendor, commission and account selections are saved per order. Changing
  admin settings affects new orders; existing payment commitments retain their snapshot.
- Duplicate callbacks do not create another invoice or receipt. A verified payment remains
  Paid if stock or accounting prevents acceptance; the admin sees a review warning and can
  retry verification after correcting the underlying problem.
- The payment window is 30 minutes. An active Cashfree payment session blocks cancellation
  to avoid cancelling while the customer pays. Unpaid expired sessions can be cancelled.
- A five-minute recovery job checks pending orders. Successful/failed/refund webhooks also
  trigger verification with Cashfree's backend API.
- The admin can check vendor status and inspect split/settlement details for recent orders.
  Reconcile actual bank deposits and Cashfree fees against the clearing account in ERPNext.
  Marketplace-side commission income and provider fee accounting are not posted automatically.

## Refunds and limits

### Troubleshooting gateway errors

Failed Cashfree HTTP calls show the operation, HTTP status, a bounded provider
error code, and an app-generated request reference. Match this reference to the
`x-request-id` in Cashfree API logs ([Cashfree request ID documentation](https://github.com/cashfree/cashfree-pg-sdk-php/blob/master/docs/Orders.md)).
The backend also writes the same safe message to
`sites/<site>/logs/local_commerce_cashfree.log` (and the Bench logs directory).
It does not record raw response bodies, request payloads, headers, payment session
IDs or credentials. Field hints are suggestions, not a confirmed diagnosis.

For an HTTP 400, record the operation and code before changing gateway settings.
Do not treat every 400 as an absent order or switch settlement modes on an existing
order: its original payment snapshot and idempotency key must stay intact.

Initiate refunds from Cashfree's dashboard. Successful refunds are fetched from Cashfree;
full refunds display Refunded, while partial refunds retain Paid and flag accounting review.
Both block further fulfilment until reviewed. ERPNext credit notes and outgoing refund
entries require administrator reconciliation; this version does not create them automatically.

This version supports INR, Indian ten-digit customer phone numbers and one shop/vendor per
order, matching the existing cart. Grand total and payable rounded total must match; orders
requiring additional ERP rounding are rejected before checkout. Vendor KYC, settlement
schedules and refund initiation remain in Cashfree. The API version is pinned to 2025-01-01.

## Validation before enabling production

On a test site, exercise success, failure, abandoned checkout, duplicate webhook, failed
accounting and retry, full/partial refunds, and both normal and scheduled deliveries. Confirm
that a paid Cashfree order never requests cash at delivery. Check the invoice, Payment Entry,
commission Journal Entry and Cashfree split amounts. Test COD and Manual UPI alongside it.

Local automated checks cover signatures, amount/currency validation, splits, duplicate
callbacks, accounting retry, cancellation and refund duplication. They do not replace a
Cashfree sandbox transaction or ERPNext integration test on a configured bench.
