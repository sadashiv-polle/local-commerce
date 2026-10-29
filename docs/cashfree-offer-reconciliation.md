# Cashfree checkout discounts and reimbursement

A successful payment may be less than the order value when Cashfree returns a successful DISCOUNT redemption. Verification requires a captured payment, matching order/payment identities and currencies, a PAID provider order, and customer payment plus unique successful discounts exactly equal to the order value. Cashback is not an upfront discount. Multiple successful payments and unexplained differences require reconciliation.

For the supplied example, ₹160 + ₹50 discount = ₹210. The supplied profile is sandbox and the payment says “Simulated response message”; this evidence does not establish a real bank debit or a reimbursement obligation.

## Operational workflow

1. In administration → Cashfree, retry verification. A valid discounted receipt is recorded as Paid, with customer cash, discount and offer IDs preserved. Unconfirmed funding remains flagged for accounting review, without posting ₹210 as cash or automatically fulfilling the order.
2. Obtain written confirmation from Cashfree identifying the offer sponsor, merchant contribution, reimbursement amount, timing, settlement references and refund treatment. Offer names and SUCCESS redemption do not prove who funds the discount.
3. Check offer settlement evidence. The app compares order-specific net settlement plus fees against customer cash. An excess is an observation, not automatic proof of a specific sponsor or bank credit. Match the UTR to the bank statement.
4. For a direct-merchant order without a marketplace GST snapshot, record the confirmed funder, written evidence and a separate INR asset account for offer reimbursement. Retry verification to post customer cash and the confirmed receivable separately and accept the order if stock checks pass.
5. Link a dedicated submitted reimbursement journal after bank receipt: debit the actual bank, credit the offer receivable for the full discount. Include the LC Order ID in remarks and a bank reference. Journals cannot be allocated to multiple orders.

Easy Split/vendor allocation, marketplace GST, partial or combined reimbursements, and discounted refunds require manual accounting review. They are not automatically posted. Refund observations use the customer's actual payment as the cap. Already-cancelled paid orders are flagged for fulfilment/refund review, not silently reopened. Recent cancelled pending/failed Cashfree orders are also checked by reconciliation.

The reimbursement link records the journal validated at that time. If that journal is later cancelled or amended, review the linked allocation before relying on it. No sponsor promise is treated as bank cash. Do not treat an unresolved discount as commission or increase vendor payouts based on presumed reimbursement.

## Deployment and validation

This change uses existing JSON audit fields; no new DocType fields are needed. Deploy backend and rebuilt frontend together, restart workers/web processes, and clear site cache through the normal release process. Validate on a sandbox Frappe/ERPNext site before production: invoice ₹210, customer receipt ₹160, confirmed offer receivable ₹50, balanced GL, stock acceptance, repeated verification without duplicate posting, and subsequent reimbursement journal. Local unit tests do not replace this native accounting integration check.

## Provider references

- [Cashfree settlement and reconciliation](https://www.cashfree.com/settlement-and-reconciliation-guide/): settlement reports, fees and bank reconciliation.
- [Cashfree terms](https://www.cashfree.com/tnc): settlement deductions depend on the merchant arrangement.
- [Cashfree One Click Checkout](https://www.cashfree.com/one-click-checkout/): offer products include bank/fintech co-funded promotions. This does not identify the sponsor of a particular payment.
