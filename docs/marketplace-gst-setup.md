# Marketplace GST setup and acceptance checks

## Before registration

Open **Admin → GST & commission**. You can save platform and shop drafts without a GSTIN. Leave **Enable this reviewed GST model for new orders** unchecked. Activation requires a checksum-valid platform GSTIN, legal identity, state, a separate platform INR Company, cost center, SAC and all required accounts. This checks format/configuration, not GST portal registration status.

Existing shops/orders keep their previous payment and tax behaviour. This feature does not turn off taxes already configured in ERPNext. Do not enter a placeholder GSTIN. Add the actual registration after it is issued and your accountant confirms the supply treatment.

## Automatic setup when adding a shop

In **Admin → Shops → Add shop**, leave **Automatically create and assign shop accounts** checked. Enter the shop's registration/GSTIN (if registered), legal name, email, business address, city, postal code, two-digit GST state, shop type, intended GST treatment and GST-inclusive commission percentage.

For an INR Company, creation provisions company-scoped LC-prefixed ledgers for commission expense, platform amounts payable, ECO GST collected, Cashfree clearing, shop bank, cash, delivery income, gateway expenses and stock adjustment. Fish shops also receive a wastage expense ledger. Compatible LC accounts are reused; conflicting/disabled accounts stop creation for review instead of being overwritten. The Company must have an active non-group default cost center, which standard ERPNext Company setup normally supplies.

Each shop receives a dedicated warehouse and selling price list. Cash, UPI and Cashfree payment modes are reused or created without changing global Company-account mappings. All operations share the shop-creation transaction: a validation failure rolls the request back.

The shop stays Draft, ordering paused, and payment methods/GST disabled. The created bank account is a ledger only. Review real banking details, gateway credentials/vendor onboarding, location pin and owner membership before opening. Platform GST accounts remain a separate one-time setup; creating a vendor shop never changes platform identity or accounts. Uncheck automatic setup for manual/non-INR onboarding.

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
