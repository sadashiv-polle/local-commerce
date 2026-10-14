# Loose fish and separately stocked packs

For independent stock, create a separate product for each selling format:

| Product | Selling mode | Price | Example receipt |
| --- | --- | --- | --- |
| Bangde — loose | By pieces (Nos) | ₹20 per piece | 30 pieces |
| Bangde — 6-piece pack | By prepared packs (Pack) | ₹100 per pack | 10 packs |
| Bangde — 15-piece pack | By prepared packs (Pack) | ₹200 per pack | 5 packs |

1. Open Products & stock → Add product.
2. Choose By prepared packs. Put the contents in the name, e.g. Bangde — 6-piece pack.
3. Create it, open Manage, and set the price per Pack.
4. Receive the number of complete packs and enter the purchase cost per pack and expiry.
5. Repeat for another pack size. Receive loose pieces on the separate Nos product.

Selling one 6-piece pack reduces 10 packs to 9. It does not deduct loose pieces or
15-piece packs. Each product has its own expiry lots, reservations, stock valuation,
and sales. Receive stock separately; there is no automatic loose-to-pack transfer.
Existing stock and orders are not converted automatically. Existing shared-stock options
remain shared; create new Pack products for this independent-stock workflow.

## Earlier shared-stock options

The following feature remains available for products that intentionally share loose stock.
Do not use it when receiving complete packs separately.


Use a product with stock unit **Nos**. Keep stock and purchase costs in individual pieces.
Do not change the stock unit on an existing Kg product with transactions; create a separate
Nos product if needed.

1. Open the shop workspace → Products & stock → manage the product.
2. Under Selling options, click Add option.
3. Enter `6 Bangde`, Number of pieces `6`, Price for the whole pack `100`.
4. Add another option: `15 Bangde`, pieces `15`, pack price `200`.
5. Leave Show this option checked, then save the product.

The same controls are available under Fish inventory → Edit market prices.
The regular per-piece price is retained as the product's base price; enabled pack options
use their own prices. Remove all pack options to return to ordinary per-piece selling.

Customers select a pack and its quantity. Two 6-piece packs cost ₹200 before configured
checkout taxes/fees and reserve 12 pieces. All packs share the same stock pool. With 20
pieces available, one 6-piece pack and one 15-piece pack cannot both be ordered.

ERPNext uses a separate reusable sales UOM such as `Pack of 6 Nos`, with conversion factor
6. This avoids rounding ₹100 / 6 into an inaccurate per-piece price. Invoices and stock
movements retain the pack-to-piece conversion. Existing order snapshots retain their prices.
There is no additional weighing step for Nos packs. Existing Kg options remain unchanged.

Verification on a disposable ERPNext site:

```bash
bench --site TEST_SITE run-tests --app local_commerce --module local_commerce.tests.test_packed_weights
```
