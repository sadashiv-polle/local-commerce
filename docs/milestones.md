# Implementation ledger

## Milestone 1 — Frappe scaffold, authentication and shop membership

Implemented files:
- Root package/build/lint metadata, MIT license, ignore rules and GitHub checks.
- `local_commerce/hooks.py`, config, module/patch manifests and install hooks.
- `LC Shop` and `LC Shop Member`: JSON schema, controllers and Bench tests.
- Namespaced Role fixtures; no custom fields or overrides on standard records.
- Policy and Frappe permission hooks, session service, session/shop APIs.
- Frappe page and one Vue workspace with server-derived membership and shop settings.
- Unit tests, frontend client tests and operational documentation.

Migration: standard DocType synchronization and idempotent membership unique constraint.
Verification evidence is recorded in `verification.md`. Bench-dependent verification remains a release gate. This milestone does not claim full phases 1–2 completion: HTTP-level authentication tests, standard ERPNext isolation, configurable staff permissions, automatic reinstall safety and broader collision checks remain outstanding.

## Next milestone — verify foundation on Frappe/ERPNext 15

Run fresh-site install, migrate, build, integration tests and uninstall/reinstall on a disposable Bench. Harden record ownership/provenance for install-created roles. Add HTTP tests for login/logout/session expiry/CSRF, REST resource access and users holding multiple roles. Extend tenant isolation to the standard ERPNext records needed by phase 3; define how shared Item and Customer masters are exposed without leaking tenant information.

## Remaining ordered milestones

3. ERPNext Item/category/warehouse APIs, company isolation, inventory validation and reservation concurrency.
4. Customer addresses, serviceability, server-priced cart/checkout and order state machine.
5. Configurable payment adapter, provider sandbox, signed idempotent webhooks and refund foundation.
6. Delivery assignment, state transitions and mobile driver interface.
7. Operating hours, capability, preparation, serviceability and delivery-pricing configuration.
8. Scheduled slots, booking/start distinction, capacity locks and batches.
9. Provider-independent routing, distances, ETA and navigation.
10. Authorized realtime tracking, GPS retention and reconnect tests.
11. Commission, fees, refunds, marketplace settlement and reconciliation.
12. ERPNext sales/invoice/payment/tax/commission accounting and reports.

Each milestone must follow the master's database → service → API → permission → frontend → jobs → tests → documentation sequence. Financial, inventory and delivery functionality is not implemented in the foundation release. Provider accounts, sandbox validation, accounting reconciliation and restore tests are required before any production-readiness claim.
