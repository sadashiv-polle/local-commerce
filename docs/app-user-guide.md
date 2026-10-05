# Local app — Setup and everyday operations

Edition: 5 October 2026

Prepared against current code; external provider and live-site operation require deployment verification.


## 1. Start here: accounts and setup order


### Which screen is which?

Local app: https://webcheckly.shop/local-commerce. This is the customer, shop and rider interface. ERPNext Desk: https://webcheckly.shop/app. Use Desk for Users, Companies, accounts, warehouses and other business master records. A role in Local does not automatically grant every ERPNext permission.


### 1. Platform administrator

Use Administrator for initial ERPNext setup, or a named account with LC Platform Administrator for Local platform controls. Use a separate named admin account for everyday administration. Do not share the Administrator password with customers or riders.


### 2. Shop owner

Create a separate User for the owner, using their real email. Give them LC Shop Owner and an enabled Owner membership for the correct shop. Use this account to manage products, orders, stock, payment review and cash handover.


### 3. Delivery person

Create a separate User with LC Delivery Person and an enabled Delivery Person membership for each shop they serve. They see assigned deliveries; membership alone does not assign orders.


### 4. Customer

Customers register through Create an account in the Local app, verify their email and sign in. They do not need shop memberships. For testing, use a separate customer email rather than the admin or rider account.


### Recommended order

Configure Company and accounting first; create shop; assign people; configure stock and prices; enable payments and delivery; add products and receive stock; configure storefront; then run one complete test order with separate customer, owner and rider logins.


## 2. Roles: what to assign and what to keep private


### LC Platform Administrator

Controls all Local shops, memberships, platform storefront and Cashfree configuration. The built-in Administrator account is also recognized. System Manager alone is not a substitute for this Local role.


### LC Shop Owner / LC Shop Staff

Owner can perform operational changes within an enabled Owner membership. Staff is read-only for shop operations; do not use Staff when a person must accept orders or change stock. Each account must also have the matching base role.


### LC Shop Settings Manager

Optional additional role for a trusted owner. It delegates restricted shop settings including COD, Manual UPI, delivery modes, fees, location and other setup controls. It does not grant platform Cashfree secrets, company changes or storefront administration. If payment setup must remain admin-only, do not give this role to ordinary owners.


### LC Scheduled Delivery Manager

Optional additional role for an owner to manage schedules/batches for owned shops. It does not grant all shop settings or the normal/scheduled mode switches. The Settings Manager role also provides schedule access.


### Assigning access

In Desk, search User, open the correct email, add the required roles under Roles & Permissions and save. Search LC Shop Member: select Shop, User, Membership Role (Owner, Staff or Delivery Person), tick Enabled and save. Membership creation adds the matching base role when missing. One user/shop membership is allowed; use separate accounts where separate duties are needed.


### Verify access

Sign out and sign back in after changing roles. Check the displayed account email. An owner must see only assigned shops and a rider only their assignments. Removing a role or hiding a schedule does not cancel existing orders.


## 3. Admin: create the business and accounting foundation


### 1. Company

In Desk, open Company and select/create the business that legally owns the shop. Configure country and currency. Current Cashfree flows use INR. Fish World and OMI Kart may have separate Companies; never choose accounts from another Company just because the account name looks similar.


### 2. Warehouse and cost center

Create/select an enabled, non-group warehouse and cost center belonging to that Company. These are required for stock and valuation. Choose the actual operating warehouse; changing it later does not move existing stock.


### 3. Chart of Accounts

Create/select leaf accounts in the same Company: stock adjustment, cash, receiving bank, and wastage expense for fish. Cashfree additionally needs a dedicated INR Bank-type Asset clearing account. Use a separate real bank ledger for settlements. The parent Bank Accounts group is not a receiving ledger.


### 4. Bank versus ledger

A Bank record such as State Bank of India names a bank institution. A Bank Account record stores account details. An Account in Chart of Accounts is the accounting ledger used for postings. Creating only Bank does not populate an accounting-account dropdown.


### 5. Mode of Payment

In Desk, create a Bank-type Mode of Payment called UPI for Manual UPI and Cashfree for gateway payments as required; Cash is used for COD. Configure company-specific default accounts where needed. Labels alone do not make an account valid.


### 6. System services

Ensure outgoing email works for verification/reset messages, site URL uses the public HTTPS domain, and scheduler/workers run for daily slots and payment recovery. Ask the server administrator to verify these. Email arrival also depends on the mail provider; it cannot be guaranteed instant.


## 4. Admin: add and publish a shop


### 1. Create the shop

Use Admin > Shops and the available shop setup controls, or search LC Shop in Desk. Enter shop name, Company, shop type (Fish or General), description and shop image. Save the record and use its internal ID only for links, not as the customer-facing name.


### 2. Inventory setup

Open the shop workspace > Products & stock and configure the shop warehouse, stock adjustment account and cost center. The app uses a dedicated selling price list. Do not attach another shop's price list.


### 3. Location and delivery area

As admin, open Shop settings. Set street, city, postal code and shop map pin; save the correct delivery radius. The map pin must be the shop's real location. Check with a nearby and an outside-area customer address.


### 4. Availability

Set Status to Active, configure weekly opening hours and turn on Accept new orders. Configure the order response period and manual/automatic acceptance where available. Being Active alone does not guarantee checkout: hours, stock, payment setup and delivery eligibility must also pass.


### 5. Delivery pricing

Set minimum item subtotal, base delivery fee, included distance, extra-distance fee and free-delivery threshold. Normal delivery uses these rules. Scheduled delivery has no delivery fee. Save each settings section using its own button.


### 6. Visibility checklist

For a purchasable product, check active shop, enabled booking mode, payment method, available stock, selling price, active/non-sold-out Item and customer delivery eligibility. Use View storefront to check the result as a customer.


## 5. Admin: Cash on Delivery and Manual UPI


### COD setup

Sign in as platform admin. Open the shop > Shop settings > Cash on Delivery. Enable COD, select the same-Company cash collection ledger and Cash Mode of Payment, then Save payment settings. A delegated Settings Manager can also access this configuration.


### Manual UPI setup

In the shop settings UPI / scan & pay section, enable the method, enter the receiving UPI ID, upload the QR image and select the receiving bank ledger plus UPI Mode of Payment. Verify that the QR and ID actually pay into that bank account. Save and check from a customer account.


### Customer UPI sequence

Customer selects Manual UPI and places the order. They should see the saved QR/UPI ID and payment amount on their order, pay through their UPI app, and upload proof. The payment waits for shop verification; a screenshot is not an automatic payment confirmation.


### Owner UPI sequence

Open Payment review or the order's UPI panel. Compare the actual bank credit with the order amount and transaction reference. Confirm receipt only when the money is present. For a Requested order, successful verification also accepts the order. Then prepare normally; no separate unpaid acceptance step is required.


### Rejecting proof

Enter a clear review note explaining what does not match, then Reject proof. Rejecting proof and cancelling an order are different actions. The customer can resolve the payment/proof issue where the order state permits. Never use invented bank references for live payments.


### COD closeout

The rider records the cash actually collected at delivery. Owner checks Cash handover and confirms the actual amount handed over. Difference Pending, Partially Paid or Overpaid needs admin accounting review; do not call a shortage reconciled or manually mark it paid just to clear the screen.


## 6. Admin: Cashfree and settlement setup


### 1. Profile

Open Admin > Cashfree. Create a Sandbox profile for testing or a separate Production profile for real payments. Enter Client ID and secret only in the admin backend-connected form. Keep old profiles for existing payment history. Never put secrets in a slide, screenshot or frontend file.


### 2. Your own shop

For Fish World if it belongs to the main merchant, choose Main merchant account / Direct merchant. Select the gateway profile, same-Company INR Bank-type Asset clearing ledger and Bank-type Mode of Payment. No Easy Split vendor ID is required in this mode.


### 3. Other vendors

Use Easy Split only for vendors onboarded in Cashfree. Enter the approved vendor ID, commission type/value and commission expense account. Commission uses the full order total including delivery and tax. Existing orders retain their original configuration.


### 4. Enable checkout

Enable Offer Cashfree at checkout for the shop and save. Configure the webhook URL shown in the admin panel in Cashfree. Complete required provider onboarding/domain setup before production. COD and Manual UPI can remain enabled separately.


### 5. Payment flow

Customer opens Cashfree checkout. Only server-verified successful payment marks Paid and automatically accepts the order. A browser success screen alone is insufficient. If payment is debited but the app is pending, refresh payment status and ask admin to reconcile before paying again.


### 6. Settlements and refunds

Configure actual bank, fee and fee-tax expense ledgers for settlement reconciliation. Enable hourly reconciliation only after checking existing manual journals. Initiate Cashfree refunds in its dashboard; cancelling a shop order does not by itself guarantee a refund. Verified full refunds and supported settlements post through the app's accounting flow; partial or ambiguous cases require admin review and may need a linked credit note.


### Testing

Sandbox does not move real money but can create real ERP documents on the connected site. Use a separate test site/Company for testing. Confirm invoice, payment and settlement entries with your accountant before live operation.


## 7. Admin: homepage, categories, photos and offers


### Where

Sign in as platform admin and open Admin > Storefront. Ordinary shop owners do not control the platform homepage. Home shows discovery content; the Shops tab shows the shop directory, search and map option.


### Promotional slider

Turn on Show slider on homepage. Click Add slide, upload a JPG/PNG/WebP photo up to 5 MB, enter a title/image description, and enable Show this slide. Repeat for up to 12 slides. Wide artwork around 1600 x 500 works well. The entire image is kept visible on phone and laptop.


### Links

App link is optional. Paste a full Local shop page URL or /store/SHOP_ID. Owner links /shop/SHOP_ID are converted to customer links. Use /categories for category browsing. Leave blank for an image with no destination. Do not paste a payment or external checkout link.


### Timing and saving

Enable automatic changes and choose 3–30 seconds. Move slides up/down or delete unwanted slides, then click Save promotional slider. Refresh and confirm the saved list. A hidden slider remains saved but is not visible publicly. Customers can hold the image to pause, release to resume, or swipe/use arrows. Reduced-motion preferences suppress autoplay.


### Offer pricing

Banners advertise offers; adding a discount to an image does not change checkout prices. Configure the actual offer/prices separately and test the checkout total. Remove or hide outdated promotional artwork.


### Categories and products

In Category menu, choose categories, upload artwork, arrange tiles and show/hide them, then save. Available categories depend on active shop products. In Saved product lists, choose Selected or Random products, title the list and save; enable its visibility toggle.


### Pin a shop first

Under Show a shop first, select an active shop and save. It appears before other shops even outside the address delivery radius; delivery restrictions still apply. Search results still respect the search text. Choose None to restore normal sorting.


## 8. Shop owner: products, prices and stock


### 1. Open workspace

Sign in with the owner account and choose the assigned shop. Use Products & stock for catalog work and Fish inventory & reports for fish-specific controls. If the shop is missing, ask admin to check the enabled Owner membership and role.


### 2. Add product

Choose Add product and enter name, category, stock unit and the supported product details. Use Nos for piece items and the appropriate weight UOM for weight-based items. Enter the actual selling price, description and product photos. Save and check its customer card.


### 3. Selling options

Where selling options/packs are configured, check each option's price and stock consumption. A fixed-price piece is not automatically repriced by its weight. Confirm the customer-facing unit and price before making the item available.


### 4. Receive stock

Use Receive stock/Add stock. Enter physical quantity, acquisition cost and reason. Fish receipts also use expiry/validity settings. This is a stock receipt adjustment, not a supplier bill; use ERPNext purchasing if a vendor invoice/payable is required.


### 5. Understand balances

On hand is physical ledger stock. Reserved is committed to orders. Sellable is what new orders may buy after reservations, expiry and availability rules. On-hand stock can be larger than sellable stock. Do not change counts merely to make a blocked order pass.


### 6. Remove or expire stock

Use Remove stock for actual wastage/damage and enter a reason. Review low-stock and expiry warnings daily. Receive fresh stock when needed. An order may reserve an expired lot even when other fresh stock exists: use available repack/reallocation controls or ask admin to inspect the reservation; do not extend expired fish validity to bypass the check.


### 7. Hide or restore

Mark sold out to pause sales without deleting stock/history; restore it when appropriate. Archive disables a product without erasing past transactions. Customers can request Notify me on unavailable items; receiving stock and availability changes must make the product genuinely sellable.


## 9. Shop owner: daily order processing


### 1. Start the day

Check opening hours, Accept new orders, sellable stock and active delivery people. Review Overview cards, Orders, Payment review and Cash handover. Use the separate Normal/Scheduled order view and status filters.


### 2. New order

Match order ID, customer, items, address, total and payment method. COD follows configured manual/automatic acceptance. For Manual UPI, review payment before progressing; for Cashfree, verified payment accepts automatically. Do not ask a prepaid customer to pay the rider again.


### 3. Prepare

Move Accepted orders to Preparing. Pack the correct products and quantities. Mark Ready when packed. Check the error if stock, payment or a reservation blocks progress; changing the visual status is not a substitute for resolving it.


### 4. Assign and hand over

Choose an enabled delivery person assigned to this shop. Hand over the correct package using the order ID. Rider pickup and Out for Delivery updates identify where the order is in the workflow.


### 5. Monitor

Use Accepted, Preparing, Ready, Picked Up, Out for Delivery and Delivered filters to find stuck work. Check normal and scheduled orders separately. Record the order ID when escalating a problem.


### 6. Cancellation

Use the cancellation action only where the app offers it, with a reason. Payment sessions, paid orders and proof under review can restrict cancellation. Cancellation does not prove money was returned; admin must review payment/refund status separately.


### 7. Close the day

Review undelivered orders, pending payment proofs, rider cash, expired stock and reports. A screenshot, a customer promise or a completed delivery alone is not accounting reconciliation.


## 10. Scheduled delivery: daily slots and batch workflow


### 1. Enable modes as admin

Shop settings > Delivery bookings: Normal only, Scheduled only, both, or neither. Neither prevents delivery booking. Ordinary owners cannot change these switches; grant Settings Manager only when you intend to delegate them.


### 2. Create a daily schedule

Use Repeat every day (times only). Enter slot name, ordering start/close, delivery start/end, maximum orders, radius, optional postal codes and products. Ordering start must precede close; close must be no later than delivery start, and delivery must end later. Times use the site timezone, normally Asia/Kolkata. Midnight delivery end may use 00:00.


### 3. Area and products

No product selection means all available shop products. If postal codes are entered, both postal-code and radius conditions apply. Scheduled delivery fee is zero, but item minimums and configured taxes still apply.


### 4. Reuse and visibility

Enable Show to customers for future bookings. Daily rules generate separate dated batches; scheduler/workers must run. Edit/delete controls apply to eligible records. Booked batches preserve customer commitments. Old batches remain history, and deletion/hiding does not erase booked orders.


### 5. Owner batch work

Open Orders > scheduled batches / Manage batch. Resolve each pending request/payment first. Use Start preparing batch and Mark batch ready when offered, confirming each stage. Cancelled orders are excluded; a blocking order may prevent advancing the batch.


### 6. Assign and deliver

Assign the ready batch to one eligible rider. Rider confirms batch pickup, then starts batch delivery at the allowed time. The recommended route is based on road travel, not guaranteed live traffic optimization. Any stop can be chosen when practical.


### 7. Finish separately

Every customer stop needs its own delivery confirmation and OTP, plus COD cash confirmation when applicable. There is no bulk Delivered action to bypass these checks.


## 11. Customer: register, choose an address and order


### 1. Account

Open Local > Create an account. Enter the requested details, verify the email code and sign in. Use Forgot password with your email if needed. Usernames are unique; the app may append random digits to the first-name-based username if needed. Check Account for your login identity.


### 2. Address

Tap Delivering to below the logo. Select a saved address or Add address. A guest signs in before saving an address. Enter recipient/contact details, address and map location accurately. A saved address must be selected; do not assume the last account's address applies.


### 3. Browse

Home contains categories, promotional slides, shops and recommendations. Shops is the shop directory. Map view shows shop locations; open a shop to see its items. Favourite saves items; Notify me requests an availability alert. A pinned shop can be out of delivery range.


### 4. Cart

Choose a product/option, check unit and price, add quantity, then open View cart. Review the selected address. Change the pin only through the address editing flow. Stock, price and delivery eligibility are rechecked at checkout. Logout clears the cart; do not use it as permanent storage.


### 5. Delivery

Choose one of the shop's enabled delivery options. For Scheduled, choose an available ordering/delivery slot during its booking window. A full or closed slot cannot be booked. Review the total and delivery fee before submitting.


### 6. Pay

COD: pay the rider at delivery. Manual UPI: pay the shown QR/ID, upload a screenshot and wait for review. Cashfree: complete secure gateway checkout and wait for server verification. If money was debited and status is unclear, contact the shop with order ID and transaction reference before paying twice.


### 7. Track and receive

Use Orders or the active-order shortcut. Choose pending/delivered/attention/cancelled tabs and status filters. Check shop, order ID, timeline, rider and available tracking. Share delivery OTP only when the rider is handing over the correct order. Use Call/WhatsApp shop for help. Buy again from an eligible past order rechecks current availability and prices.


## 12. Delivery person: pickup to cash handover


### 1. Sign in

Use your own rider account. Admin must enable LC Delivery Person plus a Delivery Person membership for the shop. Open Deliveries and select Normal or Scheduled. If empty, ask the owner to check assignment; do not log in as the customer.


### 2. Before pickup

Match order ID, shop, package, destination and payment status. Confirm pickup using the available action. A paid order has no cash due; do not infer COD from the product total alone.


### 3. Start delivery

Use Start delivery / Start batch delivery. Allow location permission and check your current-position marker. Use navigation to each customer. Keep the app active for reliable tracking; this browser/PWA cannot guarantee background location when the phone locks, the app is closed or the OS suspends it.


### 4. Arrive

At the correct customer location, tap I've arrived - Notify customer. This is an explicit rider action. Alert delivery also depends on customer notification permission/device support.


### 5. Proof and OTP

An optional delivery handover photo can be uploaded before completion where shown. Use the customer's delivery OTP and verify the order. This guide does not assume signature capture exists. For COD, record the actual amount collected. Then confirm Delivered.


### 6. Batch stops

Each customer sees tracking for their eligible Out for Delivery order in the batch. You may complete stops out of the recommended order. Complete each stop separately; finishing one must not imply all were delivered.


### 7. End of shift

Hand cash to the shop owner and reconcile the actual amount through Cash handover. Report any difference, failed delivery or payment disagreement with its order ID. Stop location sharing when work is complete and sign out on shared devices.


## 13. Reports, troubleshooting and launch checklist


### Reports

Fish inventory & reports includes relevant online/offline submitted invoices and returns. Awaiting stock cost means margin is not final. Product margin is not company net profit. Use ERPNext Profit and Loss and bank reconciliation for the wider financial picture; fees, expenses and cash differences need their own review.


### Shop or option missing

Check login role/membership, shop Active status, product visibility/stock, selected address, delivery mode, slot window/capacity and payment configuration. Refresh after role changes. Save each settings section separately.


### Slider does not save/show

Check image uploaded, title entered, interval 3–30 seconds, a supported internal link, global Show slider and per-slide visibility. Click Save promotional slider and read the exact message. If the schema update is requested, ask the server administrator to run migration; do not repeatedly recreate slides.


### 417 or other server error

Record the page URL, exact time, action and complete displayed error. An app-opening error is different from a save error. Missing frontend assets require npm build on the server. Old email errors do not identify a new slider failure. Share only relevant logs without secrets.


### Payments

For a blocked payment, record order ID, method, status and transaction/reference. Review bank/gateway evidence before retrying. Never force Paid by editing the database. Correct the underlying account/company/configuration problem and retry the supported verification action.


### Launch test

Use separate accounts to test: customer signup/reset email; save/select address; normal COD order through OTP delivery and cash handover; Manual UPI proof approval/rejection; Cashfree sandbox success/failure; daily scheduled batch; outside-zone checkout; sold-out item alert; refunded/cancelled order handling. Check both mobile and laptop.


### Daily responsibilities

Admin: configuration, user access, accounting exceptions and provider issues. Owner: stock, availability, preparation, payment review and cash. Rider: correct pickup, tracking, arrival and verified delivery. Customer: correct address, payment, proof and OTP at handover.
