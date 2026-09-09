# Owner products and inventory

This update implements a product/price/physical-stock workflow in the existing
Vue owner workspace. It does not complete orders, customers, delivery or finance
management; see `IMPLEMENTATION_STATUS.md` for the full gap analysis.

## Deployment and setup

Keep the site's normal services running. Pull the update, run `bench --site
<site-name> migrate`, `bench build --app local_commerce`, and clear site/website
caches. Fresh installations use the same after-install configuration hook. Do not
use force-install or reinstall to apply this update.

In `/local-commerce#/shop`, open a shop and select **Inventory setup**. Choose an
existing non-group, enabled Warehouse, Stock Adjustment Account, and Cost Center
belonging to the shop's Company. Standard ERPNext Company accounts, fiscal year,
perpetual-inventory settings and stock valuation configuration must be correct.
The administrator creates missing ERPNext master records through normal setup;
the app never creates arbitrary accounting accounts or modifies global defaults.

Saving setup creates one dedicated ERPNext selling Price List in the Company
currency. Repeated saves reuse it. Owners cannot attach another shop's price
list. There is one selected warehouse per shop for this workflow; switching it
changes the displayed stock location and future adjustments, not existing stock.
Historical adjustments retain their original warehouse.

## Product workflow

- **Add product:** Item name, existing category and stock UOM. The server assigns
  the shop, Company and item code. The new UI supplies a request key; same-key
  retries return the original item. Old API callers without a key retain the
  prior behavior and should migrate to keyed creation.
- **Manage → Details & price:** change name, plain-text description, selling price
  and low-stock threshold. Company, ownership and stock UOM are not editable.
  Price changes update the dedicated Item Price and add a standard audit comment.
  Product edits use the last modified timestamp to reject stale updates.
- **Mark as sold out:** pause marketplace availability. Stock stays unchanged.
  Uncheck to resume; zero available stock still shows Out of stock.
- **Archive:** disable the ERPNext Item without deleting it, its stock or history.
  Uncheck to restore. Restore an archived item before making stock adjustments.
- **Search/filter:** server-side name search, active/manual-sold-out/archive
  filters, 20 products per page. Summary totals are shop-scoped; low-stock count
  is explicitly for the current page. Prices and Bin balances are fetched in
  batches. Prices shown here are owner configuration, not a tax-inclusive quote.

Customer catalog publication and checkout remain unavailable. A product marked
Active is not automatically published by this release.

## Physical-stock operations and accounting

**Add** submits an ERPNext Material Receipt Stock Entry. Enter a positive quantity,
positive acquisition unit cost in the Company currency, and a reason. This is a
stock adjustment receipt; it does not create a purchase invoice or vendor payable.
Use ERPNext's purchase workflow when those documents are required.

**Remove** submits an ERPNext Material Issue Stock Entry for damaged, wasted or
missing inventory. Valuation comes from ERPNext, not a client selling price. A
removal is not a sale: it creates no customer invoice, revenue or payment record.
Use the future order/invoice workflow for sales. Neither action writes directly
to Bin, Stock Ledger Entry or GL Entry. ERPNext creates the stock/accounting
postings according to the Company configuration.

Quantities use the Item stock UOM. Whole-number UOMs reject fractions; other units
accept up to six decimals. Batch/serial/template items are deliberately rejected
by the simple adjustment endpoint and require standard ERPNext workflows. Zero
valuation receipts are not supported here. No backdating is accepted from Vue.

Available stock is on-hand less the larger of explicit reserved_stock and summed
Bin commitment fields supported by the installed v15 version. This is a
conservative display/check, not a checkout reservation system. A removal exceeding
unreserved stock is rejected even if ERPNext permits negative stock. Concurrent
owner mutations lock the shop and Item; stock changes also lock the existing Bin
row. ERPNext's own stock validation remains active. Concurrent operation with
other apps still needs stress testing on the target site.

## Retry, history and corrections

Each stock request carries an idempotency key. A unique SHA-256 request identifier
includes the authenticated user and shop. Reusing it with a different payload is
rejected. Authorization is checked again before replay, so revoked users cannot
retrieve the prior result. The audit record and submitted Stock Entry are written
in one request transaction with no application-level commit. An exception rolls
back the request through Frappe.

The UI retains an unconfirmed stock payload in sessionStorage under the user/shop
key. Retry uses the same payload and key, including after a refresh in that tab.
Do not start a new request to compensate for an unknown outcome: resume it first.
Browser storage is required for this retry behavior. Explicit validation failures
allow correcting the form; network/unknown failures preserve the pending request.

**History** lists workspace adjustments with actor, time, reason, warehouse,
quantity and Stock Entry reference. `LC Stock Operation` is a request/audit record,
not an inventory ledger. Normal users cannot create, edit or delete it directly.
Correct an adjustment with a new opposite adjustment and reason; app-tagged Stock
Entries cannot be cancelled through the ordinary document path. History does not
claim to include every transaction posted through other ERPNext applications.

## Authorization and schema

Owners with enabled membership can mutate only their assigned shops. Staff can
view catalog/history but cannot configure prices, edit products or adjust stock.
Drivers and customers have no owner API access. No Stock Manager role is required.
LC tenant users are denied raw Item Price, Price List, Warehouse, Bin, Stock Entry,
Stock Ledger Entry and GL Entry access, including when combined with broad roles;
narrow owner APIs return only authorized shop data. Site/platform administrators
retain their standard ERPNext permission model. Standard reports or methods that
bypass document permissions are not automatically secured by these hooks: do not
grant unrelated ERPNext report roles to tenant accounts without auditing them.

Migration adds optional warehouse/account/cost-center/price-list fields on LC Shop,
`LC Stock Operation` JSON/controller, Item fields `lc_creation_key`,
`lc_description`, `lc_sold_out`, `lc_low_stock`, and Stock Entry `lc_shop`. Existing
Items, balances and selling prices are preserved. Unassigned legacy Items do not
appear in the owner catalog. The existing Item.lc_shop ownership field remains.
Pre-migrate checks reject incompatible custom-field types and LC DocType modules.
No destructive data patch is introduced.

## Verification

Run the committed ERPNext integration tests on a disposable test site with a
working chart of accounts and fiscal year:

```bash
bench --site <test-site> run-tests --app local_commerce --module local_commerce.tests.test_owner_inventory
bench --site <test-site> run-tests --app local_commerce --module local_commerce.local_commerce.doctype.lc_stock_operation.test_lc_stock_operation
```

The tests assert actual Stock Entries, stock ledger changes, balanced Company GL
entries when perpetual inventory is enabled, same-key replay, insufficient-stock
rejection, warehouse isolation, staff and revoked-owner denial, pricing,
availability, archive behavior and raw resource denial. They have not run in the
local workspace, which has no Bench. Run the whole app suite and fresh install
checks before considering the workflow verified end to end.


### Automatic Company creation

When a platform administrator saves a new LC Shop with Company empty, the app creates
an ERPNext Company using the trimmed Shop Name. Country and currency can be supplied
on the form or inherited from Global Defaults. ERPNext creates the standard chart of
accounts and warehouses. The generated Company abbreviation is unique.
Select an existing Company explicitly to reuse it; a matching name is never silently
linked. Existing shops and later shop display-name edits do not rename Companies.
Company and shop creation share the request transaction. Run the LC Shop Bench tests
to verify provisioning with your ERPNext installation; these integration tests cannot
run in the standalone local workspace.
