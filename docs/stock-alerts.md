# Back-in-stock alerts

Sold-out products show **Notify me when available** in the shop, product details,
home product listings and favourites. Guests are asked to sign in first.
Customers can cancel using the same button.

The scheduler checks up to 200 subscriptions each minute, oldest checked first.
An alert is sent once sellable stock and a price are available (including enough
stock for a visible selling option). Archived products, manual sold-out flags,
reserved stock and expired fish stock follow the storefront availability rules.
Large queues can take longer than a minute.

Customers receive an in-app notification linking to the product. Phone push uses
their existing notification subscriptions and requires device permission.
An alert does not reserve stock or guarantee the previous price. A customer can
subscribe again when the product sells out again.

Deploy with `bench --site mysite migrate` to create LC Stock Alert and update
LC Notification. The scheduler and short queue worker must be running.
