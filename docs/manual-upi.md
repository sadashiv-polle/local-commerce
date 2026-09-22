# Manual UPI payments

After updating, run `bench --site mysite migrate` and rebuild the frontend.

In **Shop workspace → Settings → UPI · scan & pay**, the shop owner or platform
administrator can enable UPI, enter the shop's UPI ID, upload its QR image, and
choose its INR Bank account and a Bank-type Mode of Payment. If needed, create
these in ERPNext first. The ID and QR must belong to the receiving bank account;
the app cannot verify that relationship. QR upload is optional: the UPI ID and
Open UPI app link also work. Each order keeps its original payment destination.

Cash on Delivery and manual UPI can be enabled independently. Both normal and
scheduled bookings support either enabled method.

1. Customer selects UPI at checkout and places the order.
2. Shop accepts it and finalizes any required packed weights.
3. In My orders, the customer sees the final amount, QR and UPI ID. The customer
   pays externally, then uploads a JPG, PNG or WebP screenshot (up to 5 MB).
4. Shop opens the order, checks the **actual bank receipt**, enters its transaction
   reference and confirms receipt of the displayed full amount. Alternatively,
   reject the proof with a note so the customer can resolve it and upload again.
5. Approval submits the ERPNext Sales Invoice and a Bank Payment Entry. The order
   is marked Paid. Repeating approval does not create another payment. A reference
   already verified against the same bank account cannot be reused.
6. Pickup is blocked until verified. The delivery person completes delivery using
   the customer's OTP, with no cash collection or cash handover record.

Payment screenshots are private; customers can access their own proof, and the
shop's payment managers can review it. Riders do not receive the proof URL.
Owners receive a payment-review notification; customers receive the result.

There is no gateway integration, automatic bank verification, or automatic refund.
Do not approve based only on a screenshot. Resolve partial/incorrect payments
before approval. While proof is under review, packed weights and cancellation
are blocked; rejecting proof allows correction. Paid orders cannot be cancelled
or repriced through the app. Refund and paid-order cancellation workflows are
not included in this release and need administrator assistance.

## Verification

Local unit checks cover review state, access restrictions, replay protection,
duplicate references and waiting for final weights. A full ERPNext test is provided
for a **disposable test site** (not the production shop):

```sh
bench --site TEST_SITE run-tests --module local_commerce.tests.test_manual_upi
```

This verifies a UPI-only shop, private upload, bank payment and invoice submission,
blocked unpaid pickup, and OTP delivery without a COD collection.
