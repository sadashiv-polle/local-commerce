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

## O Baiii! — Goan Konkani

The existing Campaigns section includes 50 templates (20 fish seller, 15 village
conversation, 10 bargaining, 5 weekend), each in English letters and Devanagari.
English-letter copy uses `polee`. Wording is editable and should be checked for local
usage before sending. These are 50 paired templates, not 100 separate campaigns.

Choose a product, select the Goan style, set and save its actual fish type, then choose
a template and script. Fish tags are explicit administrator mappings in LC Store
Settings; names are not guessed. Bangde/Makrel share a tag. Generic fish templates
accept any mapped fish; species-specific templates require the matching tag.

The existing preview, draft, self-test and scheduling controls are reused. Audience
can be all eligible promotional recipients or eligible accounts with an order at the
selected shop. This is not a customer language or geographic preference filter.
Goan template settings let administrators disable individual templates and opt into
automatic Goan wording. Automatic Goan wording is OFF initially. When enabled it
replaces eligible automatic wording rather than adding sends; unmatched products or
times use existing English wording. Existing five-per-day and 150-minute limits apply.

Default Goan hours are 08:00–19:00 site time, configurable within a single day.
Shop opening hours must also permit sending. Optional windows are morning 08–10,
lunch 12–14, evening 17–19. Explicit lunch/dinner wording and weekend templates have
additional time/day restrictions. A schedule outside its template/window is rejected;
workers recheck eligibility and defer outside the allowed time. Pending promotional
push records expire on the next site calendar day as before. Self-tests do not enforce
production time windows and go only to the requesting administrator.

Product campaigns now require current availability when queued, during processing,
and immediately before push. Unavailable products are skipped/suppressed, not replaced
with a different product under the same text. History shows expired/suppressed counts;
LC Notification retains a suppression reason for unavailable/disabled/mismatched
campaigns at push time. Queued remains a record count, not a delivery confirmation.
Existing notification records are retained. Repeated production jobs do not create
another notification for the same campaign and recipient; explicit self-tests remain
repeatable. Delivery cannot be guaranteed exactly once across an external push service.

Opening notifications refreshes current shop/product data, including when that product
is already open. Sold-out products show the existing sold-out state. A delivered push
cannot be recalled and does not reserve inventory. Admin edits must still describe the
selected product accurately; the app cannot validate arbitrary marketing claims.

Deployment requires `bench --site mysite migrate` before using the updated app. No
campaign is sent by the migration. Run a self-test after deployment to verify device
permissions and VAPID configuration; local unit tests do not verify real phone delivery.
