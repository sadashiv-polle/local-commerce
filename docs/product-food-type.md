# Product food type

Owners and platform administrators can select **Veg** or **Non-veg** in the existing
Add product and Manage product forms. Not specified is available for unclassified
items and non-food goods. Classification is an explicit seller choice: existing
products are not automatically classified from their name, shop or category.

The customer shop shows a green circle marker with Veg text or a red triangle marker
with Non-veg text on product cards and details. The All / Veg / Non-veg sliding control
filters the server catalogue before pagination, together with search, category and
in-stock filters. All includes unclassified products; the other two choices exclude
them. Text and shape distinguish the markers as well as colour.

The value is stored on ERPNext Item in the `lc_food_type` custom Select field.
Creation, retry validation, updates and direct Item validation enforce the allowed
values. Older update clients that omit the field preserve its current value.

Deployment: pull, rebuild, run `bench --site mysite migrate` to create the custom
field, clear cache and restart. Then classify existing products through Manage.
This change does not change inventory, prices, orders or payments.
