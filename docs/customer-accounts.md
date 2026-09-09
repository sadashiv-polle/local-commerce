# Public store and customer accounts

The standalone page, session context, shop listing and customer product catalogue
are public. Owner configuration, stock history, order creation and account APIs
remain authenticated. Only active shops enabled for delivery requests are listed;
private ERP Item, Customer and Address APIs are not made public.

Guest carts are saved per shop in browser localStorage, without names, phone numbers
or addresses. Login redirects carry the current Vue route; verification emails
return to that route after password setup. Cart data survives reloads and opening
the verification link in another tab in the same browser. Another device, cleared
storage or blocked storage cannot recover an anonymous cart. Prices and quantities
from localStorage are display-only and revalidated by the server at order creation.

## Signup and verification

The Create Account form calls Frappe's native signup flow through a rate-limited
POST endpoint. Frappe sends the password setup/verification email and authenticates
the user after successful password setup. Then the Vue app calls a POST to resolve
the Customer. It does not link an existing business record merely because a guest
typed someone else's email or phone. Store signup needs outgoing email configured
and native signup enabled. No custom password database or password handling is added.

Customer linking occurs after authentication, so an unverified signup cannot claim
an existing Customer or see its history. Existing users use normal Frappe login
(including its configured authentication controls). Customer identity is derived
from the session, never selected by the customer or supplied by a request argument.

## User → Customer

`LC Customer Account` stores one canonical User-to-Customer relationship. The
Customer's standard `portal_users` relationship is also established. Customer is
shared across shops/Companies; new orders no longer create one Customer per shop.

Resolution is serialized using the User row and follows:

1. Existing canonical account link.
2. A unique explicit ERPNext Customer portal-user link.
3. A unique authenticated email match against Customer email or linked Contact email.
   Automatic email claims are limited to Individual customers without another login.
4. A historical Customer from the prior LC per-shop implementation, if available.
5. A new Individual Customer using Selling Settings defaults.

Multiple email matches, disabled customers, corporate/shared customer claims and
conflicting logins stop without creating another Customer. These exceptional data
conflicts require reconciliation by support. Existing duplicate business records
are never merged or deleted automatically. Historical LC orders are not rewritten.

Normal new website users receive LC Customer automatically. Existing ERP staff do
not receive tenant-restricting LC roles merely by visiting the store. The standard
Customer portal role/link remains available and ordering needs authentication only.

Account displays the linked customer name and paginated, filtered Sales Order
summaries for that Customer. Delivery-request history remains on My orders. Private
customer records and address documents are not sent to Guest APIs.

## Verification

Local tests cover cart persistence, shop separation, malformed storage, checkout
return URLs and storage errors. Six Bench integration cases cover new/reused
customers, cross-shop identity, ambiguous matches, Guest rejection, immutable
links and disabled accounts. Run on a disposable site:

```bash
bench --site TEST_SITE migrate
bench --site TEST_SITE run-tests --module local_commerce.tests.test_customers
bench --site TEST_SITE run-tests --module local_commerce.tests.test_orders
```

Email delivery, password setup/login, real browser cart return, concurrent linking,
public HTTP routing and ERPNext database integration have not been verified locally.
