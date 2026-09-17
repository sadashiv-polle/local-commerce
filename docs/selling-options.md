# Count and weight selling options

Use **Kg** as the product's stock unit. Stock valuation and the weight-based selling price are
both per kilogram; count options can have separate prices per piece. All options for the same product share its kilogram stock.

In **Shop workspace → Products & inventory → Manage → Details & price**, add
selling options and save. Each option has an editable name and quantity:

- **Count**: any whole number of pieces and an approximate total weight in kg.
- **Weight**: the requested weight in kg, including fractional weights.

For example, one Mackerel product can offer “5 fish” (approximately 0.5 kg),
“10 fish” (approximately 1 kg), and “1 kg (about 8–10 fish)”. These are examples;
the app does not enforce those counts or labels. Customers choose an option in
the product details and can put different options from one product in the cart.
Cart quantities count packs of the selected option.

Each count option can use **Per piece** pricing with its own price per piece, or
retain **Actual weight** pricing. Weight options use the product selling price
per kg. In **Show to customers**, choose **Weight**, **Pieces**, or **Both**;
individual options can also be hidden. Hidden options stay editable for the owner
but cannot be selected in a new customer order. At least one option must be shown.
Earlier count options retain their existing weight pricing until explicitly changed.

Weight-priced checkout lines show an estimate using the expected weight.
Piece-priced lines charge pieces × price per piece × number of packs. After
accepting the order, the owner enters the **total actual packed weight** for each
option line in the order's packing form. If a line contains two packs, enter the
combined weight of those two packs. Save to confirm the final bill. Owners can
edit these weights while the order is Accepted or Preparing. All packed weights
must be confirmed before marking the order Ready.

The price per kg is frozen when the customer orders. Actual packed weight changes
the weight-priced line quantity. For piece-priced lines, the piece quantity and
price stay fixed; the conversion to stock Kg uses the actual packed weight. Thus
piece-priced orders also require a packing weight before Ready. Native ERPNext
Sales Order lines use Nos for these sales and Kg for stock. The Nos conversion
is added automatically to the Item when piece pricing is configured. Delivery charges are recalculated using the shop's delivery
rules, and ERPNext recalculates taxes. The customer receives an order notification
and sees the final weights and total. Delivery and COD use this final bill.

Finalization cancels and amends the submitted Sales Order using ERPNext's normal
workflow, preserving its history. Insufficient stock or a failed amendment rolls
back the change. Existing products without options keep their usual ordering
flow. Reordering an option product directs customers to choose its current option
again.

Pulling code requires `bench --site mysite migrate` to install the new Item field
and order snapshot field. Rebuild the frontend and restart this bench's web group
after deployment. Automated local checks cover selling rules and cart behaviour;
the Frappe packing integration tests require an ERPNext test site.
