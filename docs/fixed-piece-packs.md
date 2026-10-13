# Fixed-price fish packs

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
