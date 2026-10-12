# Operational workspaces

Deploy with `bench --site mysite migrate` before restarting the app. New fields reuse LC Order and LC Shop; no additional transaction DocTypes are created.

## Platform admin

**Admin → Needs attention** groups unpaid online orders, refund issues, ready orders without riders, expired fish reservations and accounting issues. Counts are independent of the selected category; an order may legitimately appear in several categories. Each page shows 20 orders with oldest modified records first. COD awaiting collection is excluded from unpaid online orders. Use Open order for the exact order, or Review payment for Cashfree/cash reconciliation. The queue never changes stock, verifies payments or initiates refunds by itself.

**Admin → Settings → Rider earnings rates** sets a flat amount in each shop's company currency per completed delivery, normal or scheduled. The rate defaults to zero. It is copied to the order at delivery completion. It is not the customer delivery fee. Later rate changes never recalculate completed deliveries. These totals record earned fees, not payroll postings or evidence of a payout. Non-admin users cannot change rates, including through the document API.

## Shop owner

**Shop workspace → Overview → Shop opening checklist** automatically checks setup and has a Check again button. It checks ordering state, owner/rider memberships, delivery location, warehouse/accounts, payment selections, delivery modes/hours/slots and priced sellable stock. It reports findings without enabling ordering or bypassing checkout validations. Restricted configuration changes still require an administrator. Product inspection uses the existing bounded catalog and states how many products were inspected.

## Rider

**Delivery workspace → Delivery earnings & cash** shows all-time deliveries and recorded earnings by shop/currency, plus cash collected and cash due to hand over. Only the logged-in rider's own records are queried. Older orders with no fee snapshot are explicitly excluded from earnings. Cash with a recorded handover date is not counted as due again, even when an invoice shortfall leaves the collection in Difference Pending. Accounting differences remain visible separately.

## Customer

Order details show **Refund tracking** when provider refund evidence is available. The existing signed Cashfree webhook, manual payment-status refresh and configured automatic reconciliation update this history through server-side verification. Requested dates come from the provider. Status event dates are explicitly labelled as when the app recorded the update, not a guessed bank completion date. Unknown statuses are never shown as completed; old responses cannot downgrade SUCCESS. Partial and multiple refunds appear individually. Failed/cancelled refunds offer shop follow-up. Legacy/manual refunds without a stored history do not fabricate milestone dates. This feature does not initiate refunds or change the existing financial reconciliation process.

Cashfree reference: https://www.cashfree.com/docs/api-reference/payments/previous/v2022-09-01/refunds/get-refund

## Validation

Local checks cover authorization, parameter binding, pagination, rider isolation, invalid rates, refund identity/amount checks and stale/replayed provider responses, plus existing accounting and readiness tests. A live Frappe/MariaDB migration and real provider webhook should be verified on staging before production use.
