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

The Create Account form collects name, email, password and confirmation. It sends
an email code without creating a User. The password stays in component memory,
never browser storage. The customer enters the code to complete registration.
Codes expire after ten minutes and five attempts, and both endpoints are rate
limited. Verification uses a Redis lock and constant-time hash comparison.

After verification, native User insertion enforces the password policy, Customer
linking runs, and native login establishes the session. Existing Users are never
overwritten: they must use Login/Forgot password. A failed email send creates no
User. Native signup must be enabled and a default outgoing Email Account configured.

Customer linking occurs after email verification or existing-account authentication, so unverified signup cannot claim
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

## Custom login

App login links now open `/local-commerce#/login`, preserving the intended next
route and cart. The Vue page uses native `/api/method/login`, supports existing
OTP challenges and password-reset requests, and reloads authenticated session/CSRF
after success. Passwords and OTPs are never saved to browser storage. Password
setup links still use Frappe's native verified reset flow. External SSO/LDAP buttons
are not implemented in this custom page; configured native authentication controls
are not bypassed.

If signup reports disabled, open Website Settings and uncheck Disable Signup, then
save. The app does not override this site-wide setting during migration. Outgoing
email is still required for verification. The HTML parser warning in the reported
trace is not the cause of the signup rejection.

Custom login unit tests, frontend lint/build and Python lint pass locally. Actual
login, OTP delivery and reset emails require server verification.


Logout uses a POST to the native session logout handler, then reloads the public
store. Guest cart data remains saved; authenticated views are discarded on reload.
Two registration integration tests cover email failure and exhausted code attempts;
these need a Bench/Redis test site and have not been run locally.
