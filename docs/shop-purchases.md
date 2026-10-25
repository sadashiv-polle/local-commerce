# Shop purchases inside Local dot

Open a product's Stock form, or Receive stock in Fish inventory. Choose Add and
select how the purchase was paid. Enter the received quantity and purchase cost
per stock unit (not selling price). For fish, also set receipt validity.

- **Owner's personal money:** records an amount owed to the owner.
- **Shop cash / bank:** select the active INR cash/bank ledger in this shop's
  Company. This records a payment already made; it does not transfer funds.
- **Pay supplier later:** choose a supplier for this shop or use Add supplier in
  the same form. The Company must have an active INR default Payable account.
- **Stock count correction:** for genuine adjustments, not purchases.

One submitted Material Receipt receives the stock. A linked Journal Entry offsets
its Stock Adjustment credit and credits the owner-funding liability, selected
cash/bank account, or Supplier payable with the Supplier party. The Company must
use perpetual inventory. Existing fish lots and expiry tracking use that same
receipt. Requests keep their idempotency key and payment details on retries.

Products & inventory → Purchases & stock history lists all three purchase sources,
quantity, recorded unit cost, receipt value, stock voucher and funding journal.
Older personally funded purchases remain visible. Historical adjustments are not
reclassified automatically.

These are purchase stock receipts and journals, **not supplier Purchase Invoices**.
No purchase GST/ITC is calculated or claimed in this form. Do not submit another
stock receipt or stock-updating invoice for the same goods. Supplier tax invoices,
returns and later supplier payment/reconciliation need the appropriate accounting
workflow. Paying an existing payable does not mean adding the stock again.

Supplier records added here are restricted to the selected shop in the app's
lookup and posting validation. Existing unlinked ERPNext Suppliers are not exposed
across shops. An administrator can link an existing supplier deliberately via its
Local dot purchase shop field using a reviewed backend change; shared suppliers
must not be reassigned casually.

Deploy with `bench --site mysite migrate`, rebuild the Vue frontend, clear cache
and restart workers/web. Migration adds the supplier shop link and stock-operation
payment-account/supplier references. It does not rewrite old transactions.
