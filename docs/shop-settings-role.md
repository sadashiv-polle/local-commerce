# Delegated shop settings

Platform administrators control delivery booking modes by default. To delegate,
open ERPNext User → Roles & Permissions and assign **LC Shop Settings Manager**.
The user must also have an enabled Owner membership for the relevant shop and the
LC Shop Owner role. The settings role alone grants no shop access.

This enables that shop's COD and Manual UPI configuration, delivery modes and daily
slots, delivery fees, order acceptance, shop type, wastage account and map settings.
Platform Cashfree gateway credentials, settlement and commission configuration,
Company changes and platform storefront controls remain platform-admin-only.

An ordinary owner retains operational access, including order processing, UPI proof
review, stock, cash handover, opening hours and basic shop details. The separate
LC Scheduled Delivery Manager role retains schedule/batch operational permissions
but cannot change the shop's normal/scheduled delivery switches.

Run site migration to import the role fixture. Users should sign out and sign in
again after an administrator changes their roles.
