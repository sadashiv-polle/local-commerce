# Promotional campaigns

Admin → Campaigns supports product/shop drafts, previews, test-to-self, manual sends and scheduling. Suggested wording offers 100 distinct complete title/message pairs per category, shared with automatic campaigns, and saved wording history; no external AI provider is configured.

Enabling app notifications includes promotions. Customers can explicitly opt out in Account; opt-outs and disabled accounts are respected. Order and delivery alerts remain independent.

## Automatic promotions

The minute scheduler selects available, priced products from active shops with configured opening hours. Paused or closed shops and unavailable products are excluded. Overnight schedules use the existing shop-hours logic in site time.

Each customer gets up to five automatic notification attempts per site calendar day across all shops, separated by at least 150 minutes (2½ hours). The gap also applies across midnight. Short opening hours or unavailable stock can result in fewer than five. Product, shop and title selections rotate by date and time slot.

Manual campaigns have no frequency cap, do not count toward the automatic five, and do not change the automatic spacing. The old lc_campaign_unlimited_testing setting is no longer needed. Tests to the administrator remain unrestricted. Duplicate approval of the same campaign does not resend it; save another campaign for a repeat send.

Push delivery rechecks opening hours and consent. Deferred promotions expire at midnight. Promotional pushes use zero provider TTL to avoid storing offline messages until after closing. Actual receipt and display depend on device connectivity and provider behavior; counts are notification attempts, not guaranteed delivery.

## Reporting and deployment

Queued counts notification records; read counts in-app reads, not verified phone impressions. Completed means recipients were processed. Automatic records appear in the same campaign history. Cancelling a record prevents further sends for that record, not future automatic time slots.

Deploy with pull/build, site migrate, clear-cache and restart. The site scheduler, workers and Web Push configuration must run. Installation does not directly send messages; scheduled automatic work starts when workers run.

Verify shop hours, midnight spacing, stock availability, opt-out, five-per-day limits and manual campaigns using test accounts on the deployed site. Local tests do not verify actual phone delivery.
