# Business structure

- **Shiv Tech Works** is the platform legal Company. **Local dot** is its brand.
- **Daily Basket** is an Owned shop linked to Shiv Tech Works, with its own warehouse,
  cost centre, retail-income ledger and price list. It pays no commission to itself.
- Each **Third-party shop** creates or selects its own separate ERPNext Company.
  Its products, stock, customer invoices and settlement entries remain in that Company.
- The platform commission is accounted for separately under Shiv Tech Works using
  the existing marketplace GST workflow described below.
- The proposed single-company third-party-vendor accounting model has been abandoned.

## Creating shops

1. Create Shiv Tech Works in ERPNext with its actual legal details and chart of accounts.
2. Open Admin → Create a shop. Select **My own shop** for Daily Basket and select
   Shiv Tech Works as **Platform legal Company**. This selection reuses the existing
   platform GST Company field; it does not enable tax collection or require a GSTIN yet.
3. Enable automatic account setup for INR accounting, enter the address and other
   requested details, and optionally add a Company Bank Account. Review the Draft shop
   before enabling delivery/payment methods. Owned shops use product tax templates;
   do not enable marketplace commission GST or Easy Split for them.
4. For another business select **Third-party shop**. Choose its existing Company or
   **Create a new vendor Company**, then enter the vendor's legal business name,
   country, currency and GST registration status. Automatic setup builds the normal
   vendor accounts, warehouse and price list. Commission defaults to 7% in the form.
5. Complete GST, bank, payment gateway and membership configuration before opening.
   If India Compliance supplies a Company GSTIN field, new registered vendor Companies
   receive the entered GSTIN through normal ERPNext validation. Company addresses,
   tax templates and other native compliance requirements still need review.
6. Add shop members. Inventory account/warehouse assignments are admin-only; members
   cannot select another shop's warehouse even if an owned shop shares the Company.

A vendor cannot use the platform Company or a Company already assigned to another
shop. Owned shops can share the platform Company. Existing Legacy shops and posted
financial documents are not relinked or reclassified automatically. Changing the
business model of a shop with products/orders requires a reviewed migration.

The schema update removes only the old single-column unique Company index from
LC Shop. It does not delete Companies or change any invoice/ledger entries.

## Validation before live use

Local unit tests and frontend checks are not an ERPNext ledger certification. On a
staging site test an owned-shop order and a third-party order through payment,
delivery, invoice printing, commission, refund and settlement. Check both Company
ledgers, bank reconciliation and cross-shop access. Use Cashfree sandbox for this.

# Marketplace GST setup and acceptance checks

## Before registration

Open **Admin → GST & commission**. You can save platform and shop drafts without a GSTIN. Leave **Enable this reviewed GST model for new orders** unchecked. Activation requires a checksum-valid platform GSTIN, legal identity, state, a separate platform INR Company, cost center, SAC and all required accounts. This checks format/configuration, not GST portal registration status.

Existing shops/orders keep their previous payment and tax behaviour. This feature does not turn off taxes already configured in ERPNext. Do not enter a placeholder GSTIN. Add the actual registration after it is issued and your accountant confirms the supply treatment.

## Automatic setup when adding a shop

In **Admin → Shops → Add shop**, leave **Automatically create and assign shop accounts** checked. Enter the shop's registration/GSTIN (if registered), legal name, email, business address, city, postal code, two-digit GST state, shop type, intended GST treatment and GST-inclusive commission percentage.

For an INR Company, creation provisions company-scoped LC-prefixed ledgers for commission expense, platform amounts payable, ECO GST collected, Cashfree clearing, shop bank, cash, delivery income, gateway expenses and stock adjustment. Fish shops also receive a wastage expense ledger. Compatible LC accounts are reused; conflicting/disabled accounts stop creation for review instead of being overwritten. The Company must have an active non-group default cost center, which standard ERPNext Company setup normally supplies.

Each shop receives a dedicated warehouse and selling price list. Cash, UPI and Cashfree payment modes are reused or created without changing global Company-account mappings. All operations share the shop-creation transaction: a validation failure rolls the request back.

The shop stays Draft, ordering paused, and payment methods/GST disabled. If bank setup is deferred, the generated bank account is a ledger only. Review real banking details, gateway credentials/vendor onboarding, location pin and owner membership before opening. Platform GST accounts remain a separate one-time setup; creating a vendor shop never changes platform identity or accounts. Uncheck automatic setup for manual/non-INR onboarding.

## Bank details during shop creation

The **Shop bank account** section offers **Add later**, **Add a new bank account**, and **Use an existing Company Bank Account** (when selecting an existing Company).

For a new account enter the bank name, account-holder name, account number twice, and IFSC. Account numbers remain strings so leading zeroes are retained. IFSC receives a format check, not an external branch/ownership verification. Use the exact bank name when reusing an existing Bank master.

Creation uses ERPNext's native **Bank**, **Bank Account** and **Account** records. The Bank Account is marked as a Company account and linked to an active INR Asset ledger with Account Type Bank. The selected ledger becomes the shop's Manual UPI bank and Cashfree settlement bank; Cashfree clearing remains separate. The account holder is included in the native Account Name label together with a non-sensitive identifier to avoid name collisions.

Existing accounts must belong to the selected Company, be enabled, and have account number/IFSC details and a valid Bank ledger. Bank options show only the last four account-number digits. Company defaults and global Mode of Payment mappings are not changed. Saving the form does not update Cashfree vendor payout details or verify bank ownership; complete those separately in Cashfree.

This workflow supports Indian INR accounts. Standard ERPNext stores routing information in `branch_code`; if the installed Bank Account metadata exposes `ifsc_code` or `ifsc`, that field is populated too. Normal document validation and installed application hooks run on insert; they are not bypassed. Extra mandatory custom fields may require completion in ERPNext followed by choosing the existing account.

**India Compliance boundary:** correct banking masters do not make the custom marketplace GST invoices/CSV native India Compliance returns. Company GST registration/address, transaction tax configuration, and the custom commission/ECO reporting integration still require verification against your installed version. No automatic GSTR filing, IRN or bank verification is claimed. Synthetic demo GSTINs may be rejected by native compliance validations; do not disable validation to force them through.

References: [ERPNext Bank Account](https://docs.frappe.io/erpnext/bank-account), [ERPNext v15 Bank Account controller](https://github.com/frappe/erpnext/blob/version-15/erpnext/accounts/doctype/bank_account/bank_account.py), [India Compliance transaction setup](https://docs.indiacompliance.app/docs/configuration/sales_transaction).

## Adding or changing bank accounts later

Open the shop workspace as a platform admin, then **Settings → Shop bank accounts**. Shops created without bank details can use this section at any time. Add a new account and choose **Save only — choose later**, **Manual UPI**, **Cashfree settlement accounting**, or **UPI and settlement accounting**. Bank records and ledgers are created using the same native validation as onboarding.

All enabled Company bank accounts are listed with masked numbers. Use **Use for UPI** or **Use for settlement** to change one selection without changing the other. This never deletes old bank records, rewrites historical order snapshots, or changes Company defaults. Full bank-number corrections/disable actions remain in ERPNext Bank Account maintenance.

Changing a ledger does not update the shop's UPI ID/QR or the Cashfree vendor's real payout bank. Update those separately before accepting payments. Already-posted accounting entries remain unchanged. Pending shop Cashfree settlements currently use the selected shop bank ledger, including for older orders; reconcile or review those before switching. UPI order snapshots retain their original payment instructions.

## Platform accounts

Use the INR Company that earns Local's commission. Set up separate, active, non-group ledgers:

| Setting | ERPNext root/type |
|---|---|
| Gateway retained-funds clearing | Asset, Bank |
| Amounts due from shops | Asset; ordinary ledger, not party-control Receivable |
| Commission income | Income |
| Commission CGST / SGST / IGST payable | Three separate Liability ledgers |
| Section 9(5) CGST / SGST / IGST payable | Three additional separate Liability ledgers |
| Platform bank | Asset, Bank, separate from clearing |
| Gateway and Easy Split expense | Expense |
| GST on gateway fees | Expense |

Fee GST is expensed, not automatically claimed as ITC. Your accountant can make eligible ITC adjustments against the provider's tax invoices. Do not offset restaurant Section 9(5) liability with this expense/ITC automatically.

## Configure each third-party shop

Only platform admins can change these settings. Select Registered or Unregistered, enter legal name, full address and two-digit GST state code (Goa: 30). Registered shops require their GSTIN; unregistered shops leave it empty.

- **Legacy:** Existing behaviour; no new marketplace GST documents. Keep your own shop in this mode if it belongs to the platform Company. Do not invoice commission to yourself.
- **Exempt goods:** For supplies your accountant classifies as exempt. An exempt fish sale does not make the platform's commission exempt. This profile rejects any supply tax, including delivery tax; use a different reviewed configuration for taxable delivery/mixed supplies.
- **Seller GST:** Registered seller's existing ERPNext tax template calculates supply GST. The platform retains commission only; the seller keeps and accounts for supply GST. This does not implement Section 52 TCS or GSTR-8; determine those obligations separately before using this mode in production.
- **Restaurant 9(5):** Only eligible restaurant services, including those from unregistered restaurants. Prices must exclude GST. Remove seller/default and item tax templates: the app adds 5% once on food plus restaurant delivery charges. No mixed retail goods, specified-premises exceptions, independent platform delivery services or B2B customer GSTIN billing are implemented by this profile.

Set commission to **7**, with **Commission percentage includes GST** selected. Commission uses pre-tax item value after discounts, excluding delivery. Select the shop's commission expense ledger, an ordinary Liability ledger for amounts owed to Local and, for restaurants, a separate Liability ledger for GST collected on behalf of the ECO. Platform and shop must have separate Companies.

Cashfree third-party shops require Easy Split. Confirm merchant-borne gateway and split charges with Cashfree; this app setting does not change your Cashfree fee agreement. Unexpected vendor-borne fees fail reconciliation for review.

## Example: food INR 100, no delivery

Customer pays INR 105. Shop entitlement is INR 93. Local retains INR 12: INR 5 restaurant GST plus INR 7 inclusive commission. Commission income is INR 5.93 and commission GST INR 1.07. Gateway charges reduce Local's income, not the shop's INR 93 entitlement.

Amounts are rounded to paise. For intrastate odd-paisa tax, CGST receives the rounded half and SGST the remainder so the inclusive total stays exact. Review this rounding policy with your accountant. For interstate supplies the applicable tax is recorded as IGST using the snapshotted platform and shop states.

## Payment, invoices and refunds

- Cashfree payment verification posts the shop's existing invoice/payment and balanced native Journal Entries in the shop and platform Companies. Retained commission and restaurant GST use the platform clearing ledger.
- COD invoices post at cash collection; Manual UPI invoices post when verified. These create amounts due from the shop, not a fictitious Cashfree receipt. Use **Record shop remittance** only after the shop actually transfers the money.
- Numbered, immutable LC GST Documents hold commission invoices and ECO restaurant invoices/credit notes, backed by submitted Journal Entries. Customer order pages link restaurant invoices. Admin reports provide all PDFs.
- These are custom marketplace tax documents, not native platform Sales Invoices. They are not automatically included in India Compliance's native Sales Invoice GST reports. Reconcile the custom CSV and journals with your accountant. E-invoicing/IRN, digital signing and automatic portal filing are not implemented.
- Cashfree refunds require verified provider evidence and a matching vendor split. A full refund reverses the original commission and restaurant GST; partial refunds require an item-specific native credit note and consistent split evidence. Missing or conflicting evidence leaves an accounting issue for admin review.
- COD/Manual UPI refunds: first create and submit the original invoice's credit note and matching refund Payment Entry in ERPNext, then link them under **COD / Manual UPI refund adjustments**.
- A refund after bank settlement creates an adjustment balance; resolve subsequent bank movements using native reconciliation. Do not record another full settlement.

## Bank reconciliation and reports

Record only the merchant statement's allocation for the selected order, not an entire batch. Net receipt + gateway fees + fee GST must equal the order's retained commission and restaurant GST. Provide actual UTR, date and statement reference. Do not use this action for bank entries already posted manually. It records accounting and does not transfer money. Refunded settlements require native reconciliation.

Choose a date period and download the GST workpaper CSV. Commission is classified separately from restaurant Section 9(5) supply; credit notes have negative values and original document references. Export refuses cancelled linked journals. The CSV is an accountant-review workpaper, **not portal upload JSON**. Return-period adjustments, B2C aggregation and applicable TCS/e-invoicing requirements need accountant review.

## Staging acceptance before enabling

1. Take a site backup, migrate and configure a separate test platform/shop setup.
2. Confirm customers and shop owners cannot change GST configuration.
3. Check INR 100 food previews INR 105 before payment, and the saved invoice agrees.
4. Pay through Cashfree sandbox; confirm vendor entitlement 93, platform commission 7, restaurant tax 5, no duplicate journals on webhook replay.
5. Verify the same example with COD and Manual UPI: amounts remain receivable from the shop until remitted.
6. Reconcile a merchant statement allocation and check its actual posting date/UTR; replay must return the existing journal.
7. Test full/partial refunds, refund after settlement, duplicate webhook, wrong split, cancelled journal and changed/disabled accounts.
8. Download PDFs/CSV, reconcile all ledgers and have the accountant approve treatment before enabling real orders.

Local automated checks cover calculations, cumulative partial refunds, journal direction/balance, idempotent document posting and existing application regressions. A live ERPNext site, provider settlements and GST portal filings cannot be validated by these local tests.

Reference: CBIC Circular 167/23/2021-GST (restaurant services through ECOs); GSTN Table 15 GSTR-1 and Section 9(5) GSTR-3B advisories. Confirm current applicability before activation.

## Automatic installation setup (Local dot)

Fresh `bench --site SITE install-app local_commerce` installs now attempt the basic
structure automatically, using ERPNext's Company, Account, Cost Center, Warehouse
and Price List documents. ERPNext must be installed first. The standard Company
creation process creates its normal chart of accounts; Local dot adds dedicated
shop resources and marketplace ledgers. It never creates a Company named Local dot
or Daily Basket.

Open **Platform administration → Local dot Setup** (`#/admin/setup`), also linked
from Settings. Only platform administrators can read or run this setup.

- New legal Company: **Shiv Tech Works**, India, INR.
- Marketplace: **Local dot**, stored in LC Store Settings; `gst_company` is reused
  as the legal Company link even before GST registration.
- Default owned shop: **Daily Basket**, General, Draft, ordering and payment methods
  off. Its workspace, warehouse, price list, cost centre, retail income, delivery
  income, stock adjustment and wastage accounts are prepared.
- Separate marketplace cost centre, commission income/receivable, clearing, gateway
  expense, gateway GST expense and vendor settlement liability ledgers are prepared.
  The clearing ledger is not a real bank account. The liability ledger is a base
  ledger for settlement accounting, not an automatic payout or ledger posting rule.
  Existing commission/settlement workflows still require configuration.
- No GSTIN, registration address, bank account, gateway profile or vendor credentials
  are generated. No third-party commission rate or settlement agreement is selected.
  Existing tax settings and native defaults remain subject to administrator review.

If Shiv Tech Works already exists without an app-recorded Company link, review the
Company and explicitly confirm it in the setup page. A pre-existing Daily Basket
also requires selecting its record; it must already be an Owned shop linked to the
platform Company. Setup does not convert a vendor or historical shop. Existing
configured platform Company links are respected, even if the Company was renamed.

The saved default-shop Link survives shop renames. Repeat runs preserve populated
settings, reuse compatible ledgers, and never activate payments or overwrite bank
configuration. Incompatible existing resources stop setup for review. Creation is
transactional and serialized; a failed automatic attempt rolls back its changes,
logs an Error Log entry, and leaves setup pending. After the ERPNext setup wizard,
a pending fresh installation retries automatically. Administrators can retry from
the same page without reinstalling.

**Upgrades do not automatically create business records.** Existing sites can opt
in from Local dot Setup after migrating. Back up first. No existing invoices,
Companies or stock movements are migrated.

The nine checklist rows report saved configuration, not external verification.
GST identity still needs valid tax accounts and correct treatment; an enabled
Cashfree profile still needs a successful test transaction. Easy Split and commission
remain pending when no third-party vendors have been configured; they are not
prerequisites for own-shop direct-merchant sales. Add actual bank details through
shop settings and configure Cashfree/GST through their existing admin screens.

### Staging verification before a new production installation

1. Install on a fresh ERPNext 15 test site. Confirm exactly one Shiv Tech Works
   Company, one owned Daily Basket, separate warehouse/cost centres and INR ledgers.
2. Confirm GSTIN/banking/credentials remain blank, the shop is Draft and ordering off.
3. Repeat setup through the admin API or page: record IDs and account counts must
   remain unchanged. Rename the default shop and repeat; no new Daily Basket should
   appear.
4. Test a site with an existing, unlinked Shiv Tech Works: nothing is adopted until
   the administrator confirms it. Test incompatible Company currency/resources:
   the request must fail without replacing them.
5. Check the page and API as a shop owner/customer: both must deny access.
6. Configure real sandbox settings, then test orders and settlement accounting
   separately. Automated local tests do not replace an ERPNext database smoke test.

## GSTIN lookup in Local dot forms

Entering a complete GSTIN in Create shop or GST & commission starts a debounced,
admin-only lookup through the installed India Compliance PublicAPI adapter. Review
legal name, trade name, registration status and address, then click **Use these
details** to populate the unsaved form. Only active registrations can be applied.
It does not rename an existing ERPNext Company, choose a GST supply treatment,
enable GST, or save the form automatically. Late responses for a previous GSTIN
are discarded. Opening a page does not fetch every shop's GSTIN.

Install/configure India Compliance separately on the site and set up API access
in ERPNext GST Settings. Provider credentials remain server-side. Provider API
credits may be required. India Compliance public GST APIs do not support sandbox:
use manual entry for demo GSTINs, never fabricated lookup results. Cashfree sandbox
is independent of GST lookup configuration. Missing integration or lookup failure
shows a message and leaves manual entry available.

References: https://docs.indiacompliance.app/docs/miscellaneous/gstin_verification
and https://docs.indiacompliance.app/docs/developer-guide/sandbox .

## Native commission billing (version 2; opt-in for new orders)

Existing orders and journal-based GST documents are not migrated or re-invoiced.
The setting is disabled by default. Configure and validate a staging Company
before enabling it in **Admin → GST & commission → Native commission billing**.
This is a new posting model, not a retrospective repair of historical balances.

### Required setup

1. Use Shiv Tech Works as the platform Company. Keep vendor Companies separate;
   owned shops do not pay commission to their own Company.
2. Retain the existing GST identity, supply treatment, rates, income accounts,
   tax accounts, bank and clearing settings. Confirm the applicable SAC and GST
   treatment with your accountant; no test GSTIN is created by this feature.
3. Select a native INR **Receivable** control account for commission Customers.
   Do not change the type of the old ordinary shop-receivable asset account.
4. Select a separate **Liability** account for commission advances.
5. Create/select a non-stock sales service Item with the reviewed SAC. Use a
   fractional service UOM (not a whole-number-only UOM). Billing units are ₹1
   each: ₹50 taxable commission is 50 service units; this permits exact native
   partial credit quantities without exhausting a one-unit invoice on the first
   partial refund.
6. For each vendor, select a dedicated billing **Customer**, with matching GSTIN
   or no GSTIN for an unregistered vendor. Complete its native billing address,
   tax category and other India Compliance details in ERPNext. Never share a
   billing Customer across shops.
7. For each vendor Company, select a separate **Asset** account for prepaid
   marketplace commission. Retain its commission expense and platform-payable
   liability accounts. Input GST credit is not automatically claimed.
8. Set payment terms (0–90 days). Enable native billing only after a staging
   invoice, credit and collection pass ERPNext/India Compliance validation.
9. Optional: enable monthly statement and weekly overdue emails. Set each shop’s
   billing email. This is off by default; SMTP/Email Queue must be operational.

New GST-enabled orders freeze the billing configuration and commission rate.
Changing the toggle or rates later does not change those orders. Existing
non-GST/Legacy shops continue their prior flow; this release does not silently
convert their tax or commission model.

### Posting and settlement

- Cashfree verification: debit retained-funds clearing, credit deferred service
  income and output GST on the advance. Vendor: debit prepaid commission,
  credit its gateway clearing. No platform commission revenue yet.
- Delivery: issue the platform’s native commission Sales Invoice. Allocate the
  advance to its receivable, reverse the advance-tax posting to avoid charging
  output tax twice, and recognize vendor commission expense against prepaid.
- COD/Manual UPI delivery: issue the platform invoice and record vendor expense
  against its payable. COD cash remains shop money. The agreed commission base
  is discounted item value before tax, excluding delivery; cash shortages remain
  collection exceptions and do not silently change this agreement.
- Admin → Commission & statements → Record receipt: record a completed full or
  partial shop bank transfer. Creates the native platform Payment Entry and a
  matching vendor payable/bank journal. Same invoice + bank reference retries
  are idempotent; differing retries are rejected. Do not enter a transfer twice
  through this screen and native ERPNext.
- Cashfree bank allocations remain the existing verified-statement workflow.
  Invoice settlement through clearing does **not** imply a completed bank payout.
- For version-2 restaurant COD/UPI orders, the legacy remittance button now
  remits **only Section 9(5) GST**. Pay commission through native invoice receipts.
- Delivery invoice failures appear in Needs attention → Accounting and retry in
  the background. They do not undo delivery. Failed jobs rotate through the queue.
- Linked native invoices/payments/journals cannot be cancelled independently;
  use credit/refund flows or an accountant-reviewed reversal of both Companies.

### Refunds and reports

Approved full/partial refunds reverse the relevant commission. Partial GST
refunds require a submitted unpaid product credit note **before** approval;
its item/delivery/tax allocation determines the vendor split. Native commission
credit quantities and cumulative GST-head rounding prevent over-reversal.
Manual return completion invokes the same commission reversal service.
Physical stock return remains separate; perishable goods are not automatically
restocked.

Shop owners see only their shop’s commission screen. Admin sees shop-wise
balances, period totals, verified bank allocation references, native invoice
PDFs, payment history and CSV statements. Legacy journal documents remain
visible but do not pretend to have native invoice outstanding balances.

Native invoices are issued per delivered order. Monthly statements summarise
those invoices and never issue a second charge. On the first day of the month,
opt-in emails queue the previous month’s statement; Monday reminders cover
outstanding invoices from the previous 365 days. Older balances need native
ERPNext Accounts Receivable aging. Dispatch is deduplicated under a shop lock;
Email Queue retries remain Frappe’s responsibility.

Download the **advance GST adjustments** workpaper alongside the invoice GST
workpaper. It separates advance receipts, advance refunds and invoice offsets.
These are accountant-review exports, not GST portal JSON or automatic filing.
Native invoice GST totals and advance offsets must be reconciled by return
period before filing.

### Compliance boundaries and staging checks

Commission GST, restaurant Section 9(5) and GST TCS are different liabilities.
**TCS deduction/registration/GSTR-8 automation is not enabled by this change.**
The admin TCS classification review CSV separates supply treatment, payment
collection method, supplier registration and commission GST for accountant
review. It uses order-creation dates, not collection/return filing periods, and
does not calculate a TCS liability.
Supply eligibility, consideration collected by the operator versus shop-collected
COD, applicable registration and effective rates require a reviewed TCS design;
never apply commission GST or restaurant tax as a substitute for TCS.
This setup must not be treated as a complete GST filing implementation.

Confirm invoice timing, tax on advances, place of supply, SAC, eligible input
credit, vendor registrations and product-specific treatments with your CA.
The default per-order invoice plus monthly statement avoids assuming that
monthly collection permits delaying every tax invoice until month-end.

References:
- [CBIC invoice rules](https://cbic-gst.gov.in/gst-invoice-rules.html)
- [Cashfree Easy Split](https://www.cashfree.com/docs/api-reference/payments/latest/split/easy-split-overview)
- [GST portal Section 9(5) advisory](https://tutorial.gst.gov.in/downloads/news/gstr_3b_sec_9_5_advisory_19_07_22.pdf)

Run native tests only on a disposable staging site, after migration:

```bash
bench --site staging-site run-tests --app local_commerce --module local_commerce.tests.test_commission_billing
```

The native test fixture checks ERPNext GL/receivables with a non-Indian INR
platform Company; it does not certify India Compliance/GST classification.
Separately test a configured Indian staging Company: online payment → delivery
→ invoice → settlement; COD → partial and full receipts; full and repeated
partial refunds; duplicate events; two vendor shops; invoice PDF; and both
intrastate/interstate tax reporting. Do not use live credentials for this test.
