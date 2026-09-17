# Fish-shop inventory and market pricing

## Enable a fish shop

A platform administrator opens **Shop workspace → Shop settings**, selects
**Shop type: Fish**, selects a **Fish wastage expense account** from the shop's
Company, and saves. The expense account must be enabled, a ledger rather than a
group, and have Expense as its root type. Other shops retain their existing flow.
Finish or cancel active orders before changing the shop type. Once lots exist,
the shop type and warehouse are fixed so their stock history cannot be detached.

Fish inventory applies to **Kg products in Fish shops**. Create a product in
**Products & stock** with unit Kg. A Fish shop defaults new products to the Fish
category and Kg. Non-Kg products in that shop continue using ordinary inventory.

## Daily prices and customer choices

In **Fish inventory & reports → Market prices**, edit a fish's price per kg,
count options and price per piece. Choose Weight, Pieces, or Both for customers;
individual offers can also be hidden. Counts, pack sizes and labels are editable.
Count offers can be priced per piece or by actual packed weight. Price and offer
changes are recorded with their time and author. Changing today's price never
reprices an existing order. Existing orders keep their frozen prices and choices.

Fish without configured offers start with a 1 Kg weight option. Edit it or add
your own offers; its final bill still requires the actual packed weight.

Weight prices are finalized using the actual packed weight. Piece prices retain
the agreed piece quantity and price; packed weight determines the amount removed
from shared Kg stock. Each option line needs its combined packed weight before
Ready. See [selling options](selling-options.md).

## Receipts, validity and existing stock

In **Stock & expiry**, choose **Receive stock**, enter Kg, receipt cost per Kg,
validity in hours and a reason. A submitted ERPNext Material Receipt is created,
with a separate expiry lot and movement record. Default validity can be configured
on each fish and overridden on a receipt. There is no automatic freshness default:
the owner sets it. A fresh receipt never extends an older lot's validity.

When enabling a Fish shop with existing stock, use **Track existing stock** to
declare its remaining validity. This tracks the untracked warehouse quantity;
it does not receive inventory or post accounting entries a second time. Existing
reservations must be cleared first. Already tracked or expired lots cannot be
renewed through this operation. Untracked stock is excluded from customer ordering.

New orders reserve unexpired lots by earliest expiry first. Later orders and
manual removals cannot take those reservations. Acceptance, Ready and pickup
check that reserved stock is still valid. Packed-weight confirmation reallocates
stock using the final weights. Cancelling an order releases its lots. Pickup
consumes those lots and the native Delivery Note reduces warehouse stock.

## Expiry and wastage

Expired stock is automatically excluded from new orders, even without a scheduled
job. It remains physically on hand until the owner records a movement. On an
expired lot, click **Mark remaining stock as wastage**, confirm the quantity and
reason. The unreserved quantity can be posted; reserved expired stock requires
cancelling or repacking its order first. Orders already Ready may need cancelling
if their fish expires before pickup.

Wastage posts a submitted ERPNext Material Issue to the configured wastage expense
account, reduces that lot's remaining quantity, and keeps an immutable audit trail.
Partial wastage is supported. **Remove stock** records a separate unexpired-stock
removal, not a sale or expired-stock wastage. Requests carry retry keys to prevent
duplicate receipts, issues, wastage and opening tracking after a network failure.

Manage these fish stock movements through the app. Direct stock receipts, issues,
stock reconciliations and deliveries involving these fish are blocked to prevent
changes bypassing the expiry ledger. Native accounting valuation reposts remain
available. Stock postings are preserved; use opposite movements for corrections.

## Reports

**Fish inventory & reports → Reports** supports date ranges up to 366 days:

- Opening, received, issued and closing Kg, plus closing stock value.
- Invoiced fish Kg and piece quantities, and product revenue at actual invoice prices.
- Cost of invoiced fish using the corresponding native Delivery Note valuations.
- Wastage Kg and cost from native stock ledger issues.
- Other removal cost, gross profit, and profit after stock losses.
- Delivery revenue shown separately from product revenue.

Product revenue excludes taxes. Profit after stock losses is product revenue less
invoiced fish cost, wastage cost and other removal cost. It is an inventory margin,
not full Company net profit: overheads, rider payments and COD differences are not
allocated automatically. Delivery fees are reported separately and excluded from
that product margin.

Sales follow invoice posting dates; their cost matches the associated deliveries,
including a delivery posted in an earlier period. Stock movements follow native
stock ledger posting dates. Pickup is a stock movement, and delivery confirmation
creates the invoice; an unbilled dispatch is therefore not counted as a sale.
ERPNext's daily GL profit may differ while a dispatch remains uninvoiced. Cost
uses the configured ERPNext valuation method and reflects valuation reposts, not
today's retail price or an invented estimated cost. Multiple options from one
fish are grouped before matching delivery costs, preventing duplicate costs.

## Deployment and validation

Pull the code, run `bench --site mysite migrate`, rebuild the frontend, clear site
and website caches, and restart only `frappe-benchs-web:`. No other bench needs
changes. Local checks cover expiry boundaries, fractional validity, reservations,
earliest-expiry-first selection, pricing choices and cart persistence.

On a disposable ERPNext test site, run:

```bash
bench --site YOUR_TEST_SITE run-tests --app local_commerce \
  --module local_commerce.tests.test_fish_inventory
```

Integration tests exercise native receipt/wastage postings and replay, expired
reservations, daily-price preservation, delivery consumption and realized margin.
They require ERPNext and migrated Local Commerce and have not run in the local
workspace. Do not run fixture-creating integration tests on a live customer site.
