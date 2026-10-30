# Promotional campaigns

Administrators use Admin → Campaigns to choose a shop/product, draft and preview a message, save it, test on their own account, and send or schedule. Customer sends require confirmation. Suggest wording uses a fixed product-name template; no AI provider is configured. Images, audience segments and purchase attribution are not included in this first version.

Customers opt in under Account → Product updates & offers. Consent defaults off and is separate from browser push permission and transactional alerts. Opt-outs are checked before generating notifications and again before phone delivery. Delivered notifications cannot be recalled.

The audience is snapshotted on approval. The scheduler processes 100 recipients per campaign per minute, between 09:00 and 20:00 in the site time zone. Scheduling inputs also use site time. Disabled users, opt-outs and customers already sent two campaigns in the preceding seven days are skipped. Test messages do not count. Repeated approval does not restart a campaign; transaction locks and cursor progress prevent repeated notification creation.

Queued counts notification records, not confirmed phone delivery. Read counts in-app read flags. Completed means all recipients were processed. Push failures use existing error logging. Cancelling stops further generation and pending phone sends, but does not remove notifications already created.

## Deployment and verification

Run pull/build, then `bench --site mysite migrate`, clear cache and restart. The migration creates campaign/preference DocTypes and notification fields. Installation does not send messages. The scheduler, workers and existing Web Push setup must run.

On the deployed site, opt in a test customer and enable phone notifications. Save a draft, test to the administrator, then approve a customer campaign and verify its deep link. Check opt-out, the two-per-week limit, scheduling and cancellation. Order alerts should remain unaffected.

Local tests cover authorization, consent, frequency limits, quiet hours, repeated approvals and batch progress. Real Frappe migration and phone delivery still require site verification.
