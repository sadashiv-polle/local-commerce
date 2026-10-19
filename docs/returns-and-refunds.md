# Returns and refunds

Customers can request a return from a delivered order. They describe the items
and reason. This release keeps one auditable return case per order; subsequent
questions about the same order should go through the shop rather than creating
another automatic refund. Pre-delivery cancellation remains the existing workflow.

Shop staff with write access can add a review (condition, received items and a
recommendation). Platform administrators see pending cases in **Needs attention →
Return requests**, open the order, and approve or reject with a reason. Approval
is not delegated to shop owners. The customer sees the reason and dated progress.

## Cashfree

- Full means the original paid total (including paid delivery charges and taxes),
  less previously confirmed refunds. Gateway fees are not deducted from this amount.
- Partial requires an explicit positive amount no greater than that remaining balance.
- A second confirmation displays the amount before **Approve and send refund**.
- Production profiles send real refunds; sandbox profiles call sandbox only.
- The approved request, amount, original vendor allocation and refund ID are persisted
  before a background worker calls Cashfree. Retries reuse the same refund ID,
  payload and idempotency key. Successful and pending external refunds consume the
  available balance. Unknown outcomes remain for administrator review.
- A five-minute job recovers queued/processing work; signed webhooks and existing
  server verification update the refund timeline. Only provider success means
  **Refund completed**. Processing does not promise a bank credit date.
- Easy Split refund vendor amounts are proportional to the original saved vendor
  share; a full original-amount refund reverses that entire share. No current-shop
  commission setting is substituted. Provider eligibility/balance restrictions can
  still prevent a refund and require review in Cashfree.
- A failed/cancelled provider refund is not silently replaced by a new refund ID.
  **Check / retry same refund** checks that case, including uncertain timeouts.
  If Cashfree requires a new refund after a terminal failure, resolve through its
  dashboard and existing accounting reconciliation; this release deliberately does
  not create an additional refund automatically.

The existing full-refund credit note/Payment Entry handling runs after verified
success. Partial refunds require selecting and submitting the appropriate native
credit note and linking it under **Admin → Cashfree → Refunds & accounting entries**.
An accounting error does not erase a confirmed provider refund or send it again.

## COD and Manual UPI

The app does not initiate bank/cash refunds for these methods. An administrator
arranges payment, submits the return credit note and customer refund Payment Entry
in ERPNext, then uses **Record completed manual refund** with both references.
The app checks supplier Company, customer, original invoice, currency, paid amount,
credit settlement and payment allocation before recording **Manual refund recorded**.
This label is an accounting record, not provider confirmation. No original payment
status is rewritten to pretend that Cashfree verified a manual transfer.

## Returned inventory

Refund approval never returns stock to sellable inventory. Automatically generated
refund credit notes have `update_stock=0`. The manual-record action also requires
such a credit note. Review physical returns separately; perishable or spoiled goods
must not be automatically restocked. Use the existing validated inventory/wastage
workflow with the appropriate evidence. The original order remains Delivered;
return and refund status are separate.

## Deployment and sandbox acceptance

Run site migration to add the read-only return audit/status fields and refresh
scheduler hooks. Back up before deployment. Test on a staging site:

1. Customer A cannot request a return on customer B's order or before delivery.
2. Only the correct shop staff can review; only a platform administrator can approve.
3. Full and partial refunds use the displayed paid amount; pending external refunds
   block an excessive approval at execution time.
4. Simulate a worker timeout/retry: only one provider refund with the same ID exists.
5. Success webhook updates the customer's timeline; partial refunds stay Paid with
   the refunded amount shown until total successful refunds reach the original total.
6. Verify full credit/payment postings, partial credit linking, commission reversals,
   and unchanged sellable stock in ERPNext. Review the provider split in sandbox.
7. Confirm invalid/unrelated manual Payment Entries and credit notes are rejected.

Reference: https://www.cashfree.com/docs/api-reference/payments/latest/refunds/create-refund
Local unit tests use mocked provider/database calls; they do not prove live gateway
or native ERPNext posting behaviour. No refunds were executed during development.
