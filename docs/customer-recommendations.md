# Customer storefront picks

Logged-in LC Customers see a “Your everyday picks” carousel before admin product lists when eligible products exist. Guest visitors and accounts with no completed orders keep the normal storefront.

A lightweight frequency model learns from up to 200 delivered orders placed in the previous 180 days. Each item counts once per order. Recent purchases have a 60-day half-life, and purchases placed on the current weekday receive twice the weight. This avoids quantity/pack-size bias and lets old habits fade. Ranking uses the site date/timezone.

Only the authenticated user's history is queried. The endpoint accepts an optional saved address, never a user/customer ID. Addresses must belong to that login. Suggestions use current public product pricing and stock, omit unavailable items, and exclude shops outside the saved address delivery radius. Up to eight suggestions are shown. There are no browsing trackers, external AI services, training jobs, or additional subscription costs.

Run standalone ranking checks with `.venv/bin/python -m unittest discover -s tests`. Run identity checks on a disposable ERPNext v15 site with `bench --site TEST_SITE run-tests --app local_commerce --module local_commerce.tests.test_recommendations`. Server integration checks require a configured Frappe site.
