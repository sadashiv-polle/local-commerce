# Google sign-up and login for Local dot

Google login uses the installed Frappe v15 OAuth implementation. No Google client secret, Google password or token exchange is handled in Vue. Email/password login remains available. New Google accounts are Website Users; the existing customer resolver creates/links their customer record when they use customer features. Existing shop/rider memberships are not assigned or changed by this feature.

## Administrator setup

Finish the fresh ERPNext and Local dot setup first. Sign in as Administrator (or a System Manager with permission to configure Social Login Key).

1. In Google Cloud Console / Google Auth Platform, create/select your project. Configure branding, support email, audience and your real application homepage/privacy details. Use External audience for customers outside your organisation. Follow the console's testing/publication requirements; add test users where required for your test configuration.
2. Create an OAuth client with application type **Web application**.
3. Add this exact **Authorized redirect URI**:

   ```text
   https://webcheckly.shop/api/method/frappe.integrations.oauth2_logins.login_via_google
   ```

   Do not add a hash route or a trailing slash. This is the backend callback, not the Vue login page. Google requires an exact match to the URI sent by Frappe.
4. In ERPNext search **Social Login Key** → New. You can also use Local dot Admin → Settings → Google sign-in settings.
5. Select **Google**, keep provider name **Google** (record ID `google`), and retain Frappe's generated Google URLs and basic email/profile scopes. Keep the default callback path shown above.
6. Paste the client ID and secret into the backend fields. Enable Social Login. Set **Sign Ups: Allow** if new customers should register with Google. Deny permits existing users only. Save. Never put the secret into Vue or send it through chat.
7. In **Portal Settings**, set the default role to **LC Customer**, **Customer**, or leave it blank. Do not choose a staff/admin role. The Local dot authorization-start endpoint refuses elevated default roles.
8. Ensure the public host is correct:

   ```sh
   bench --site mysite set-config host_name https://webcheckly.shop
   bench --site mysite clear-cache
   ```

The configured button appears on Login and Create Account. The button obtains an authorization URL from the backend only when clicked, then opens Google in the same browser. Frappe handles OAuth state, code exchange, user creation/linking and its session cookie; it redirects back to a restricted Local dot path. Account disabling and provider signup policy remain managed by Frappe. This feature does not override Frappe's OAuth callback, global login policy or MFA behavior; verify those against your installed Frappe version before offering Google login to privileged users.

## Acceptance checks before public launch

- Fresh Google account: returns to Local dot, can finish customer profile/address, has no shop/rider/admin permissions.
- Existing account with the same email: customer/order history is reused; no duplicate account is intentionally created by this app. Review Frappe's native email-based linking policy.
- Disabled user cannot log in; Sign Ups Deny blocks new users.
- Existing shop owner/rider retains their work role and normal app landing behavior.
- Google login from checkout returns to the relevant app page; cart remains saved.
- Cancelled consent, expired/replayed state and provider failures never create a successful Local dot session. These errors are handled on Frappe/Google's native pages; use the app's email login if needed.
- Test desktop, Safari/Chrome and the installed home-screen app. Google may reject embedded webviews; use the system browser in that case.
- With Google disabled, email login still works and the Google button is hidden on the next page load.

A live Google round trip requires your configured OAuth client; the repository's unit tests do not establish that the credentials/domain/consent screen are correct.

References:
- https://developers.google.com/identity/protocols/oauth2/web-server
- https://github.com/frappe/frappe/blob/version-15/frappe/utils/oauth.py
- https://github.com/frappe/frappe/blob/version-15/frappe/integrations/doctype/social_login_key/social_login_key.py
