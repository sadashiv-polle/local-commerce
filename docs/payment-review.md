# Shop payment review

Owners and platform administrators can open **Shop workspace → Payment review**.
The API requires write access to that shop before reading any orders.

- **UPI proofs:** Manual UPI orders awaiting verification, with existing proof
  review controls. Verify actual bank receipt before confirming.
- **Pending / failed:** Pending or failed Cashfree payments on orders that are
  neither cancelled nor delivered. Refresh payment status uses server verification.
- **Accounting issues:** Cashfree orders with a recorded accounting error. Correct
  the accounting setup before retrying verification; do not charge customers again.
- **Refund history:** Cashfree orders with a recorded refunded amount. This is not
  an unresolved-refund queue: the app does not currently track completion of manual
  accounting reconciliation. Initiation stays in Cashfree, and ERPNext credit notes
  and refund entries require administrator reconciliation.

Queues show 20 orders per page, oldest first. Changing category refreshes the list;
successful payment review also refreshes it. Cash handovers remain in their existing
section. No new accounting documents or payment statuses are introduced.
