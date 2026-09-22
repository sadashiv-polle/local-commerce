# Normal and scheduled delivery

Deploy with `bench --site mysite migrate`, build frontend assets, clear caches and restart
this bench's web and workers. Enable this site's scheduler for automatic compilation.
Existing shops retain their normal delivery flag; scheduled delivery starts disabled.

## Admin setup

Open Shop workspace → Settings → Delivery bookings. Only platform administrators can
change either enable switch or create/edit slots. Shop owners and platform administrators
can assign an entire ready batch.
Normal and Scheduled switches are independent. Both off prevents delivery checkout.
The existing normal delivery prices, opening hours and processing remain in place.

Create a dated slot in the displayed site timezone. Specify ordering start/end, delivery
start/end, capacity (1–30 orders), a radius, optional postal codes, and optional products.
Blank products means all available shop products; blank postal codes means radius only.
The radius is measured from the shop. When postal codes are supplied, both restrictions
must pass. Delivery periods for the same shop cannot overlap. Set future dates explicitly;
slots do not recur automatically.

Times and eligibility can be edited before bookings. Once a slot has any bookings, they
are locked to protect customer commitments; disable bookings and create a new slot when
these need to change. The enable checkbox remains editable. This does not cancel already
placed orders. The slot is also available as **LC Delivery Slot** in Frappe Desk.

## Checkout and orders

Customers browse without login and see only enabled booking types. Scheduled slots show
both the ordering window and delivery period. Slots outside the ordering window or at
capacity cannot be booked. Checkout rechecks the mode, dates, capacity, eligible products,
address zone and stock under a shop lock. Existing request keys remain idempotent.

Scheduled delivery fees are always zero, including legacy packed-weight repricing.
Configured product taxes and minimum item subtotal still apply. Cash on Delivery remains
the supported payment method. Scheduled booking does not follow the normal weekly opening
hours; it follows its own dated ordering window. An active shop with configured location,
warehouse, prices and payment accounts is still required.

Stock is reserved at order placement. Fish reservations exclude lots expiring before the
scheduled delivery period ends. The owner still accepts/prepares individual orders.
Unanswered scheduled orders time out after the ordering window closes plus the shop's
response interval, rather than immediately after placing an advance booking.

## Batches and routes

One slot is one shop's batch. At cutoff, the scheduler marks it compiled and queues route
preparation. Capacity is capped at 30 orders; create separate non-overlapping delivery
periods for more orders. Once all non-cancelled orders are Ready, the admin can assign the
whole batch to an enabled delivery person belonging to the shop.

The rider sees scheduled batches in Deliveries. The route uses the existing trusted HTTPS
OSRM endpoint (`lc_routing_url`, ending in `/route/v1/driving`) and its corresponding Table
service. A nearest-neighbour heuristic uses asymmetric road travel times from the shop,
then draws a continuous road route through those stops. This is a recommendation, not a
claim of a mathematically optimal route or live traffic prediction. See the
[OSRM API](https://project-osrm.org/docs/v5.24.0/api/).

Each stop has navigation and a button opening its existing order controls, including
pickup, start delivery, OTP confirmation and COD collection. Any stop can be completed
first. Start delivery is gated by the configured delivery start time. Refresh route after
completing stops to exclude delivered/cancelled orders. Routing failures never complete or
cancel orders; individual order controls remain available. No new map provider or API key
is required. For production capacity, configure a suitable hosted/self-hosted OSRM service.

## Validation

Local unit checks cover all four enable combinations, window boundaries, capacity,
product and shop restrictions, administrator access, and road-time sequencing.
`local_commerce.tests.test_scheduled_delivery` includes ERPNext integration checks for
free scheduled vs charged normal delivery, retries, capacity and scheduled-only booking.
Run integration checks only on a disposable test site. Test real mobile maps, scheduler,
rider OTP/COD, and simultaneous final-slot bookings on a staging server before rollout.

## Confirm each batch stage

After the ordering cutoff, owners use Shop workspace → Orders → Batch progress.
Each request must first be accepted or rejected individually. Then **Start preparing batch**
and **Mark batch ready** each show one confirmation for all eligible orders. An unaccepted
request blocks later batch stages. Cancelled orders are excluded.

After assignment, the delivery person uses **Confirm batch pickup** and **Start batch delivery**
above the scheduled route. These preserve per-order stock, expiry and delivery-start checks.
A failed order rolls back the whole stage; retries skip orders already advanced. GPS sharing
can be resumed through the existing live tracking controls.

Delivered remains a per-customer action requiring the customer's OTP and cash confirmation.
There is no bulk Delivered action that bypasses those checks. The rider may choose any stop.

## Reuse slots

The admin list retains past and hidden slots, with pagination. **Show to customers** changes
only booking visibility, not existing orders. Expired slots remain unavailable to customers
even when checked. **Reuse for another day** copies the slot into a new unsaved form and
defaults to tomorrow in the shop timezone. Choosing a new delivery date shifts the ordering
and delivery dates together while preserving their times and any overnight ordering window.
Review and save the new slot to open bookings. Old orders, batch status and dates stay intact.
Slots without bookings can still be edited directly; booked slots offer reuse instead.

## Shared batch GPS

Starting batch delivery requests device location and starts one GPS watcher. A position update
is written to every Out for Delivery order in that slot assigned to the authenticated rider.
Updates are throttled per order (at least 10 seconds; browser timer is 12 seconds), and each
customer receives only their own order's location event. Other batches, other riders,
not-yet-started and completed orders are excluded.

The batch route shows the rider's current location. Completing the order originally used to
start tracking does not end tracking for remaining stops. Refresh restores the saved session,
and explicit Stop sharing still stops it. The browser must have location permission and stay
active; a browser app cannot guarantee continuous background GPS when the phone suspends it.

## Recurring daily slots

Platform administrators can create **Daily time slots** in the shop delivery settings.
The form defaults to **Repeat every day (times only)**: enter ordering start/close
and delivery start/end, products, area and capacity once. The **Show to customers
every day** checkbox enables or hides that schedule. Times use the site timezone;
ordering and delivery are on the same day, with `00:00` supported as delivery end
at the following midnight. Dated one-off slots remain available.

`LC Delivery Schedule` stores the reusable time-only rule. Saving it generates
separate `LC Delivery Slot` batches for today and tomorrow. The existing minute
scheduler keeps tomorrow's batch ready automatically; enable the site scheduler
and keep workers running. A deterministic schedule/date ID and the shop lock
prevent duplicate daily batches. Guest GET requests never create records.

Changes update unbooked daily batches only. Booked batches retain their timing,
products, area and capacity; toggling visibility still stops new bookings without
cancelling existing orders. Past batches and order history are retained. Legacy
dated slots are not automatically converted: create a daily rule once, and disable
any overlapping unbooked dated slot if necessary. Migrate the site before using
this feature to install the new DocType and daily-schedule link.

## Selected owner access and deletion

Grant **LC Scheduled Delivery Manager** in Desk → User → Roles, in addition to
**LC Shop Owner** and an enabled Owner membership. Migration creates this role;
it is never assigned automatically. These owners can configure normal/scheduled
booking modes, create and edit daily schedules, change visibility and delete
schedules only for their own shops. Platform administrators retain access to all
shops. Shops stay normal-only unless scheduled delivery is explicitly enabled.
Existing customer commitments are not cancelled when a user's role is removed.

Daily schedule cards appear before the creation form with **Edit times & settings**,
**Show to customers every day**, and **Delete schedule**. Deletion asks for confirmation,
removes empty generated batches, and hides/unlinks booked batches while retaining
their orders and fulfillment history. One-off slots can be deleted only without
any order history; booked slots can be hidden instead. Edit scrolls to the populated
form. Changes to booked daily batches remain restricted as described above.
