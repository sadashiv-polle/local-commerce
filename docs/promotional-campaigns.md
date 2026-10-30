# Promotional campaigns

Administrators use Admin → Campaigns to choose a shop/product, draft and preview a message, save it, test on their own account, and send or schedule. Customer sends require confirmation. Suggest wording uses a fixed product-name template; no AI provider is configured. Images, audience segments and purchase attribution are not included in this first version.

Enabling app notifications includes promotions, as explained in the permission prompt. Existing enabled push subscriptions also qualify when there is no explicit promotion preference. Customers can opt out under Account → Product updates & offers; explicit opt-outs override push subscriptions and leave transactional alerts enabled. Opt-outs are checked before generating notifications and again before phone delivery. Delivered notifications cannot be recalled.

The audience is snapshotted on approval. The scheduler processes 100 recipients per campaign per minute, during the selected shop’s configured opening hours in the site time zone. Scheduling inputs also use site time. Disabled users, opt-outs and customers already sent a promotion today are skipped. Test messages do not count. Repeated approval does not restart a campaign; transaction locks and cursor progress prevent repeated notification creation.

Queued counts notification records, not confirmed phone delivery. Read counts in-app read flags. Completed means all recipients were processed. Push failures use existing error logging. Cancelling stops further generation and pending phone sends, but does not remove notifications already created.

## Deployment and verification

Run pull/build, then `bench --site mysite migrate`, clear cache and restart. The migration creates campaign/preference DocTypes and notification fields. Installation does not send messages. The scheduler, workers and existing Web Push setup must run.

On the deployed site, opt in a test customer and enable phone notifications. Save a draft, test to the administrator, then approve a customer campaign and verify its deep link. Check opt-out, the one-per-day limit, scheduling and cancellation. Order alerts should remain unaffected.

Local tests cover authorization, consent, frequency limits, quiet hours, repeated approvals and batch progress. Real Frappe migration and phone delivery still require site verification.

## Unlimited testing

Set `bench --site mysite set-config lc_campaign_unlimited_testing 1` and restart workers to bypass the daily cap for campaigns site-wide during testing. Opt-outs, disabled accounts, quiet hours and duplicate-send protection still apply. Create a new campaign for each repeat send. Restore the normal limit with `bench --site mysite set-config lc_campaign_unlimited_testing 0` and restart. Test-to-myself already has no daily cap.


## Automatic daily promotions

The minute scheduler also chooses an available, priced product from an open shop and generates a category-based message. Product/shop ordering and five titles rotate by date. All consenting, enabled accounts are considered; one promotion record per customer per site calendar day across shops is the normal limit. Approved campaigns run first and count toward that limit. The unlimited testing flag bypasses the cap for manual campaigns only; automatic campaigns always keep the daily limit.

Shops without opening hours, paused shops, disabled shops and shops without a sellable product are excluded. If no shop is eligible, no daily promotion is generated. Automatic records appear in Campaigns and can be cancelled for the remainder of that day.

Push delivery rechecks shop hours. A message delayed until after closing waits for another opening on the same calendar day; old pending messages expire at midnight instead of accumulating. Promotional pushes use zero provider TTL so offline devices do not receive stored promotions after closing. Actual display/delivery cannot be guaranteed by the app and depends on the device and push provider. This is one daily delivery attempt, not a guarantee of receipt. Transactional notifications and explicit administrator test sends keep their existing behavior.

Deploy with a site migration before restarting workers: campaign and notification tracking fields were added. Verify overnight schedules, paused shops, zero stock, opt-outs and daily limits on a staging/test account before relying on production delivery.
