# Cancellation refunds

Permitted Cashfree cancellations verify the provider order and successful payment before saving cancellation. Customers may cancel Requested or Accepted orders; shop managers and platform admins retain the existing pre-pickup cancellation states. Preparation and delivery transitions remain protected.

The cancellation transaction records a refund case and queues the worker after commit. The scheduled return worker recovers missed enqueue events. It requests the remaining actual customer payment, subtracting completed refunds. A provider discount is not cash paid and is not refunded to the customer. Existing pending or unexplained refunds block cancellation until reviewed.

The refund worker reuses its persisted payload, refund ID and idempotency key. It checks provider history before POSTing. Failed or uncertain requests become Needs review; an administrator can use Check / retry same refund. Never create another refund manually merely because a request timed out.

Submitted invoices and receipts are retained. Their Sales Order is closed instead of cancelled, and existing refund accounting posts credit/refund entries after provider confirmation. Discounted receipts or partial historical refunds may still require accounting review; bank refund completion and accounting completion are separate.

Cash on Delivery without collection needs no refund. Manual UPI and collected cash cannot be automatically returned through the Cashfree API; existing manual review controls remain in place. Delivered orders continue through the return workflow.

Deploy the code, build the frontend, clear cache and restart workers. No new database fields are introduced. Verify in Cashfree sandbox before production use, including owner/customer/admin cancellation, retries, refund status and ERP credit entries. Existing cancelled orders are not retroactively refunded by this change.
