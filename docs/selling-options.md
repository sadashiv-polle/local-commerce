# Count and weight selling options

Use **Kg** as the product's stock unit. Stock valuation and the selling price are
both per kilogram. All options for the same product share its kilogram stock.

In **Shop workspace → Products & inventory → Manage → Details & price**, add
selling options and save. Each option has an editable name and quantity:

- **Count**: any whole number of pieces and an approximate total weight in kg.
- **Weight**: the requested weight in kg, including fractional weights.

For example, one Mackerel product can offer “5 fish” (approximately 0.5 kg),
“10 fish” (approximately 1 kg), and “1 kg (about 8–10 fish)”. These are examples;
the app does not enforce those counts or labels. Customers choose an option in
the product details and can put different options from one product in the cart.
Cart quantities count packs of the selected option.

Checkout shows an estimate using the selected option's expected weight. After
accepting the order, the owner enters the **total actual packed weight** for each
option line in the order's packing form. If a line contains two packs, enter the
combined weight of those two packs. Save to confirm the final bill. Owners can
edit these weights while the order is Accepted or Preparing. All packed weights
must be confirmed before marking the order Ready.

The price per kg is frozen when the customer orders. Actual packed weight changes
the line quantity, delivery charges are recalculated using the shop's delivery
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
