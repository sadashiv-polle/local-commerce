# Fresh Local dot setup and personally funded stock testing

Use a **separate disposable site**, not an uninstall/reinstall on the current business site. Uninstalling Local Commerce does not reset ERPNext Companies, Stock Entries, invoices or GL history. Do not delete posted stock/accounting tables with SQL.

## Basic installation

After pulling this release and building assets, create the test site from the bench directory:

```sh
bench new-site localdot-test.local
bench --site localdot-test.local install-app erpnext
bench --site localdot-test.local install-app local_commerce
bench --site localdot-test.local migrate
```

The prompts request database administrator access and a new site Administrator password. Configure a separate hostname/port for this site with your hosting setup. Do not change the production site's default routing just to test. If you use India Compliance, install the matching version-15 app on the test site before testing tax setup.

Sign in as Administrator. Complete ERPNext's initial setup if prompted, then open **Local dot Setup**. If initialization was deferred because ERPNext was not ready, retry setup there. An existing Company named Shiv Tech Works requires explicit identity confirmation; it is not silently adopted.

Fresh installation creates or safely links:

- **Shiv Tech Works**: India, INR, standard ERPNext chart of accounts.
- **Local dot** marketplace settings linked to that legal Company.
- **Daily Basket**, an owned shop, initially Draft with orders/payments disabled.
- Dedicated shop warehouse, shop cost centre, retail income, stock adjustment, fish wastage and delivery income accounts.
- Separate marketplace commission, clearing, gateway charges and vendor settlement accounts and cost centre.
- **LC Stock Funding Payable <shop ID>**: liability for purchases paid personally by the shop owner. This is repayable funding, not an automatic capital contribution and not a supplier invoice.

No money/opening stock is posted by installation. GSTIN, bank details, gateway credentials, commissions and settlement activation remain manual admin setup. Repeated setup reuses compatible accounts and preserves existing shop names and live settings. Existing incompatible accounts cause an actionable error rather than being rewritten.

## How to enter stock

In Products → Adjust stock or Fish inventory → Add, select the funding source explicitly:

- **Purchase paid personally by shop owner**: quantity and actual unit cost. Creates one Material Receipt plus a linked Journal Entry: debit Stock Adjustment, credit the shop's Stock Funding Payable. Combined result: debit inventory, credit owner funding payable. No purchase-related credit remains in expenses. No GST credit is inferred from the lack of a supplier bill.
- **Stock count adjustment — not a purchase**: genuine physical count correction. Uses Stock Adjustment and therefore affects profit. Do not use for purchases or assume it records supplier payment.
- **Business cash/bank or supplier-credit purchases**: use ERPNext Purchasing, with the appropriate supplier/payment documents. Do not receive that stock a second time in this form. For tracked fish, adopt existing stock to track expiry instead of adding it again.

Pack quantities are whole packs; loose quantities use the product stock UOM. Unit cost is per pack/piece/kg matching that UOM, not selling price.

The stock history shows the funding source and Journal Entry reference. Repeating the same request does not create another receipt/journal. Funding journals linked to immutable app stock operations cannot be cancelled alone. Use reviewed correcting entries if a purchase was entered incorrectly; do not simply remove stock to erase the funding liability.

## Wastage

Set the shop's fish wastage account to its **LC Fish Wastage** expense account. Depreciation is rejected for fish wastage. Mark only physically expired/spoiled stock as wasted; a removal posts debit wastage expense and credit inventory. Historical Fish World vouchers are not automatically reclassified.

## First test and expected accounting

1. Add 10 pieces at ₹10 cost each, personally funded.
2. Confirm stock 10 / value ₹100; Stock Adjustment net ₹0 for this receipt and funding payable ₹100 Cr. Profit remains ₹0 before sales/expenses.
3. Retry the same pending request: stock and payable must remain unchanged.
4. Sell/deliver 2 pieces at ₹15 each, without tax/fees: revenue ₹30, COGS ₹20, stock 8 / value ₹80; profit ₹10 before other expenses.
5. If one remaining piece genuinely expires, waste it: wastage ₹10 and stock 7 / value ₹70. Depreciation must remain unchanged.
6. Re-run Local dot Setup: no additional shop, warehouse, account, stock or funding balance should appear.
7. Test customer payment, cancellation and refund separately in Cashfree sandbox before enabling real payments.

Native integration test (disposable site only, test records may be created):

```sh
bench --site localdot-test.local set-config allow_tests true
bench --site localdot-test.local run-tests --app local_commerce --module local_commerce.tests.test_owner_inventory
```

Verify the Trial Balance, Stock Balance and GL before live use. Local unit tests do not substitute for running ERPNext stock/accounting integration on the installed version.
