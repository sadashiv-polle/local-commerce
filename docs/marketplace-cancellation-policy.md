# Marketplace cancellation policy v1

## Activation and compatibility

Run `bench --site <site> migrate` before using the new screens. In Admin → Cashfree, edit the gateway profile. Confirm the provider configuration and enable **marketplace cancellation policy for new orders**. Set each participating Easy Split shop's commission to 7%. GST-inclusive/exclusive treatment and the existing commission basis remain explicitly configured in GST settings. Old order snapshots, COD, Manual UPI and ordinary delivered-item returns keep their existing workflows.

Cashfree must have **no static vendor splits**, merchant-borne payment gateway charges, and a split-after-payment window that covers the longest supported delivery period. Confirm this on the actual sandbox/production merchant account. The app does not change these account-level provider settings. An application status cannot override automatic splits or payouts initiated independently in the Cashfree dashboard. No credentials or live provider settings were changed by this implementation.

For policy orders the create-order payload omits `order_splits`. The worker submits the immutable vendor allocation only after OTP-confirmed delivery, at least two minutes after delivery (a conservative interval satisfying Cashfree's two-minute payment-success delay). Missed jobs recover every five minutes. A rejected cancellation request does not block subsequent delivery. Vendor split acceptance and bank settlement confirmation are separate states. Unexpected existing provider splits stop release for review rather than creating another split. A split window that expires requires provider reconciliation; the app never bypasses that failure with an untracked transfer.

## Cancellation amounts

Amounts in the policy and ledger are integer paise. Percentages round half-up; the 15% preparation component is the exact remainder after the rounded 85% refund, so paise are conserved. Provider payloads convert to rupee numbers only at the HTTP boundary.

The refund basis is the verified **customer payment**, including paid delivery/taxes, not an unfunded offer discount. Actual fees come from the payment-specific Easy Split reconciliation transaction: PG service charge, PG service tax, split service charge and split service tax. Missing values are unknown, never assumed to be zero. The fee and tax components remain separately recorded. No estimated percentage is substituted.

| Cancellation | Customer | Shop | Platform commission on cancellation |
| --- | --- | --- | --- |
| Customer, Requested/Accepted | Paid amount less actual gateway charges | No compensation | 0 |
| Shop/admin, any order stage | Full paid amount | Bears actual gateway charges | 0 |
| Customer, Preparing/Ready/Picked Up/Out for Delivery, approved by both parties | 85% of paid amount | 15% remainder less gateway charges | 0 |

The shop owes any fee excess over compensation; the customer's promised 85% or 100% refund is not reduced. Before preparation, a fee exceeding payment yields a zero customer refund and a shop receivable for the excess. If no payment was captured, no provider refund is sent. An active or unresolved payment attempt must first expire/resolve so a cancellation cannot be followed by an unnoticed capture.

A shop cancellation after a known delivery split includes an explicit refund split reversing that vendor allocation, including if the provider already settled it. Customer refunds remain subject to Cashfree processing/balance availability; they are not labelled completed because an HTTP request was accepted. Existing external/partial refunds, mismatching vendor allocations and unresolved return cases require reconciliation to avoid over-refunding.

## Requests and permissions

Customers can request only their own cancellations. Direct customer cancellations use the order status read again under the shop/order locks; a race with Preparing becomes an approval request. Only an enabled shop Owner membership can approve for the shop. An administrator approves separately. The same person cannot supply both approvals. Staff and riders cannot approve or cancel through the new endpoints.

An outstanding post-preparation request pauses fulfilment. Either rejection resumes the original order state. A shop/admin can override a pending/rejected customer request with a shop cancellation, which refunds 100%, not 85%. A completed/rejected financial case is not silently overwritten. Physical goods already dispatched are not returned to sellable inventory automatically.

Customers and owners use the Cancellation & settlement panel on orders. Admin → Cashfree → Marketplace cancellations & settlement holds provides approvals, order history, retry controls and settlement checks.

## Financial durability and ledger

`LC Order` stores the immutable policy snapshot, cancellation JSON/state and settlement state. `LC Marketplace Event` is append-only, with a unique event key and balanced debit/credit postings in paise for payment, cancellation allocation, charges, refund and vendor adjustments. `LC Marketplace Operation` stores one immutable payload per order/action with a unique operation key. Native permission rules do not allow direct mutations to either financial workflow.

The operation is committed as Unconfirmed **before** its provider POST. Refunds use a stable `mp_...` refund ID and idempotency key; the worker checks refund history, payment identity, amount and other refund reservations before sending. A success event is written once. Duplicate clicks, workers and callbacks do not generate another refund reference.

After refund success, net preparation compensation is credited from merchant to vendor with an Easy Split ADJUSTMENT; gateway costs owed by the shop are debited from vendor to merchant. There is no 7% commission on either compensation instruction. Cashfree response references, amounts and directions are checked. A transfer timeout remains Unconfirmed. Admins can explicitly retry only the original persisted instruction with the same documented Cashfree idempotency key. No new transfer is silently substituted. Insufficient balances remain reviewable obligations. Provider transfer charges, if any, remain in the stored provider response and require separate reconciliation; they are not silently deducted from the agreed customer refund.

The operational cancellation ledger is separate from ERP statutory bookkeeping. **Do not use the ordinary proportional item-return GST/commission reversal for a policy cancellation.** Existing invoice/receipt documents are preserved, and Cashfree accounting flags the case for accountant-reviewed cancellation credit notes and full commission reversal. This release does not invent the GST treatment of retained cancellation charges or automatically submit those tax documents. The refund can be bank-confirmed while native bookkeeping remains pending.

## APIs

All methods are under `local_commerce.api.cancellations`:

- POST `request(order, reason)` — immediate cancellation or dual-approval request.
- POST `decide(order, decision, note, role)` — Shop/Admin approval or rejection.
- GET `queue(start)` — paginated admin workspace.
- GET `activity(order)` — authorized case/events; provider operation payloads are admin-only.
- POST `retry(order)` — check/recover the existing financial workflow.
- POST `retry_operation(order, operation_name)` — explicit retry of one Unconfirmed instruction, unchanged identity/payload.
- POST `settlement_check(order)` — provider reconciliation; record settlement IDs/UTRs only on confirmed evidence.

No cancellation endpoint accepts a client-selected refund amount, compensation amount or commission.

## Verification before activation

Standalone tests cover paise conservation, excessive/zero fees, fee identity and missing evidence, distinct approvals in either order, rejection, customer/owner stage restrictions, a Preparing race, duplicate requests/refunds, conflicting refund history, durable-before-send intent, timeouts, and premature release prevention. Frontend tests/lint/build must pass.

This checkout has no Frappe/ERPNext runtime or live Cashfree test credentials. Run site-backed tests and sandbox scenarios before enabling the profile: migrate DocTypes, create/pay/cancel at each stage, approve in both orders, run concurrent Preparing/cancellation requests, interrupt workers after POST, verify same-key recovery, settle a delivered order, cancel an already-split order, and verify provider balances plus ERP review handling. Check zero-fee UPI, offers, missing fee evidence, insufficient vendor balance, provider failures and rejected requests followed by delivery. Confirm the backend scheduler is enabled.

## Provider contracts reviewed

- [Split after payment](https://www.cashfree.com/docs/api-reference/payments/latest/easy-split/split-after-payment)
- [Create refund](https://www.cashfree.com/docs/api-reference/payments/latest/refunds/create-refund)
- [Vendor transfers and adjustments](https://www.cashfree.com/docs/api-reference/payments/latest/easy-split/create-on-demand-transfer)
- [Order/vendor reconciliation](https://www.cashfree.com/docs/api-reference/payments/latest/easy-split/get-split-and-settlement-details-by-orderid-v20)
- [Vendor settlement reconciliation](https://www.cashfree.com/docs/api-reference/payments/latest/reconciliation/vendor-reconciliation-api)
