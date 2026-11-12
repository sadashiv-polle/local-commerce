# Cashfree vendor management

Platform admins can open Cashfree settings → Easy Split vendor management.

Select a gateway profile first; its stored environment and credentials determine
the Cashfree account. Vendor IDs are scoped to that profile. Creation and editing
support bank or UPI payout destinations, contact details, KYC text fields,
verification, dashboard access and settlement schedule IDs. Empty text fields on
update are omitted. Verification/dashboard checkboxes are explicitly submitted.
After creation, enter the vendor ID in the shop payment settings and save.
Changing a provider payout destination does not change the ERP bank ledger.

Vendor details, KYC document status, balances and date-filtered reconciliation
can be fetched from Cashfree. Reconciliation currently displays the first 25
records; full exports and KYC document uploads remain in the linked dashboard.
Existing order verification, refund and accounting workflows remain in their
existing app sections. This is not a generic Postman request runner: legacy
static splits, deferred-settlement APIs and vendor deletion are not exposed.

On-demand transfers and adjustments require a review then confirmation.
The server persists an LC Cashfree Transfer before submitting. Once submitted,
the same record cannot send a second request. Accepted means Cashfree accepted
the request, not that a bank settled it. Unconfirmed requires checking Cashfree
before creating another request; no automatic retry is performed. The request
ID, creator, time, payload and response are retained. These actions do not
automatically post ERP journals. Match them through the existing reconciliation
process or reviewed manual accounting.

Deploy with bench --site mysite migrate before using transfers.

Validation: local unit tests and frontend build only. Verify against your
sandbox profile before using production. No provider credentials are sent to
the browser. API calls use version 2026-01-01.

References:
- https://www.cashfree.com/docs/api-reference/payments/latest/easy-split/create-vendor
- https://www.cashfree.com/docs/api-reference/payments/latest/easy-split/update-vendor-details
- https://www.cashfree.com/docs/api-reference/payments/latest/easy-split/create-on-demand-transfer
- https://www.cashfree.com/docs/api-reference/payments/latest/reconciliation/vendor-reconciliation-api
