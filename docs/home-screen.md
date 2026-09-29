# Customer home screen

The home screen provides an address selector, combined shop/product search, active-order shortcuts with short order IDs, categories, shop cards, and a List / Map switch. On phones it also provides Home, Shops, Orders and Account navigation. The saved-cart button appears only when the cart contains items.

## Shop cards

Cards reuse the shop's opening hours, delivery toggles, minimum order, free normal-delivery threshold and scheduled delivery slots. Scheduled delivery remains free. Cards show the earliest enabled, non-archived slot whose ordering window has not closed and which has capacity. Customers still choose a slot in the shop, where product and delivery-area eligibility is checked.

Add a storefront photo in **ERPNext → LC Shop → your shop → Shop Photo**. Upload a public image and save. Private images are not published. Without a photo, the card shows a storefront illustration and shop type.

Delivery times are the shop's configured site-local times, rather than the customer's device timezone. Dates are shown with booking cutoffs. Daily schedules continue to use the existing batch-generation job.

## Browsing and address selection

An address is never selected automatically on login. An explicit selection is remembered for that login session. Saved-address discovery uses the existing customer ownership checks. Without an address, customers can browse active shops; checkout determines delivery eligibility.

Search matches shop names and products, with separate paginated results. Home categories are restricted to enabled categories that have enabled sales items in an active shop. Recommendations appear below shop browsing.

## Deploy

Pull the changes, build the frontend, run `bench --site mysite migrate`, clear the site cache and restart Bench. Migration is required for the optional Shop Photo field.
