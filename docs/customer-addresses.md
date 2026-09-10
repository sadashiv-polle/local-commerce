# Saved customer addresses and nearby shops

Authenticated customers manage Home, Work, and Other addresses from the Vue
account page. Each address belongs to exactly one authenticated User and its
linked ERPNext Customer. The first address becomes the default automatically;
choosing another address makes it the only default. Removed addresses are
archived so they are no longer offered for discovery or checkout.

Each address contains a recipient, phone, street, city, postal code, latitude,
and longitude. Coordinates can be entered manually or chosen on the map. Device
location requires HTTPS. Customers can keep up to 20 active addresses.

The storefront remembers only the opaque selected address name in local storage.
Nearby discovery resolves that address on the server after checking ownership.
It never accepts another User's saved address. Active shops are ordered as:

1. Shops that accept delivery to the address.
2. Shortest straight-line distance from the address.
3. Shop name.

A shop is serviceable only when Cash on Delivery and delivery are enabled, the
customer postal code is listed by the shop, both map pins are present, and the
distance is inside the shop's configured radius. Checkout repeats the postal-code
and radius validations, so storefront labels are informational and cannot bypass
order validation.

Checkout pre-fills the selected saved address. The order continues to store an
immutable address snapshot, so later edits to the saved address do not change
existing orders.
