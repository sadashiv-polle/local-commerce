# Local Commerce

An installable Frappe custom application targeting **Frappe 15 + ERPNext 15**.
The app and Python package are `local_commerce`; the Frappe module is `Local Commerce`.

**Status: foundation milestone implemented; Bench validation pending. This is not the complete marketplace or a production-ready release.**
The [master specification](docs/master-specification.txt) is the scope of the full build.
See [milestones](docs/milestones.md) for implemented and outstanding work.

## Included in this milestone

- Frappe session login via the standard `/login` route, with CSRF-protected mutations.
- Five namespaced LC roles, an ERPNext Company-linked `LC Shop`, and `LC Shop Member`.
- Role AND active membership checks for shop read/write; platform-only membership administration.
- Permission query hooks for lists, document permission hooks, and controller validation.
- One Vue 3 application, with Vue Router, served by Frappe at `/local-commerce`.
- Shop settings, pagination, error/loading/empty states, and standard Frappe Version auditing.
- Local authorization tests, API-client tests, Bench integration tests, lint/build CI.

Company, User, Role and Version remain standard ERPNext/Frappe records. No standard DocTypes or fields are overridden. `LC Shop Member` records the marketplace relationship that a standard Role cannot express. One shop per independent Company is enforced for this release.

## Prerequisites

Use a working Frappe Bench with Frappe **15.x** and ERPNext **15.x**, a supported Python runtime (Python 3.11 recommended for the test environment), Node 22, npm, and the database/Redis services required by your Bench. This app does not install Frappe from PyPI: Bench owns the framework dependencies. Use a disposable staging site first.

## Installation

From your Bench directory, after publishing this app root as the `local_commerce` Git repository:

```bash
bench get-app https://github.com/<owner>/local_commerce.git
bench --site <site-name> install-app local_commerce
bench build --app local_commerce
bench --site <site-name> migrate
bench restart
```

For a local checkout use `bench get-app /absolute/path/to/local_commerce` instead of the Git URL. The directory containing this README is the repository root; do not add a wrapper project directory. The local workspace can have a different directory name, but the published repository and installed app must be `local_commerce`.

The root `build` npm script is invoked by Bench's app build workflow. It emits content-hashed files and a manifest under `local_commerce/public/frontend`. Frappe's asset symlink serves them under `/assets/local_commerce/frontend/`. These generated files are intentionally ignored by Git; build on each deployment before routing traffic to the new version. The page reads the manifest, so no filename or domain is hard-coded.

## Site setup

1. Complete ERPNext Company setup, including currency, country and accounts, using ERPNext's standard setup tools.
2. As Administrator, assign `LC Platform Administrator` to a named platform administrator.
3. Create an `LC Shop` in Desk and choose its Company. Each Company has at most one shop.
4. Create named Frappe Users and assign `LC Shop Owner`, `LC Shop Staff`, `LC Delivery Person`, or `LC Customer` as appropriate. Use standard password reset/invitation and authentication settings; no passwords are seeded.
5. Create an `LC Shop Member` for each owner, staff member or driver, selecting the corresponding membership role. Users must already have its matching LC Role.
6. Sign in through `/login`, then visit `/local-commerce`.

Shop owners may update name, status and description. Only platform administrators can create shops, change Company or manage membership. Disable membership to revoke shop access immediately. Staff is read-only in this milestone; configurable staff operations come with later domain services. Driver and customer accounts authenticate but have no operational features yet.

**Standard ERPNext permissions are not provisioned or hardened by this release.** Do not assign broad ERPNext roles to tenant accounts and assume LC membership restricts those roles. LC roles confer access only to the two LC DocTypes. Standard Company, Customer, Item, Warehouse and financial-document isolation must be implemented and tested before enabling their APIs or granting their Desk roles. Platform administrators need separate standard ERPNext authorization to manage Companies and Users.

## Frontend development and build

```bash
npm ci
npm run lint
npm test
npm run build
```

Use `bench watch --apps local_commerce` for the Bench environment and `npm run build -- --watch` in the app root for Vue changes, then reload the Frappe-served page. This keeps requests on the authenticated site's origin and exercises CSRF. `npm run dev` starts Vite tooling but is not a standalone authenticated app; use the Frappe page for end-to-end development. No frontend environment variables or secrets are required. Vue Router uses hash navigation under the namespaced page to avoid interfering with Frappe routes.

## Tests and migrations

```bash
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
python -m build
npm run lint
npm test
npm run build
bench --site <test-site> set-config allow_tests true
bench --site <test-site> run-tests --app local_commerce
```

Use a disposable test site. The integration suite creates real ERPNext Companies and Users. Tests exercise cross-shop document/API denial, Company reassignment denial, membership revocation, uniqueness and Version auditing. Pure tests are not substitutes for the Bench integration suite or HTTP-level security tests.

Schema is defined by committed standard DocType JSON. Roles are fixtures declared in `hooks.py`. Install/migrate hooks add the `(shop, user)` database uniqueness constraint idempotently; there are no business-data patches yet. Future data patches belong in `patches.txt`. Installation rejects preexisting LC DocType/module/role or Web Page route collisions rather than overwriting them. Python and frontend stay inside their own package and CSS root.

## Operations

Keep the standard Frappe web, Redis, database, workers, scheduler and Socket.IO processes healthy. No custom scheduled jobs or realtime channels are registered in this milestone. Later payment, reservation and delivery phases require tested worker/realtime recovery; simply running those processes does not provide those features.

Use the normal Frappe production deployment behind HTTPS; separate development, staging and production sites. Keep secrets in site configuration or Password fields and retain the Frappe encryption key securely. Never put site data, credentials or backups into this repository. Configure request limits, login throttling and authentication policy through Frappe and the deployment proxy.

Before upgrades, back up database and files using `bench --site <site-name> backup --with-files`, copy encrypted backups off-site with a defined retention policy, and test restoration into an isolated site. Record measured RPO/RTO with the deployment owner; this repository has not validated a recovery target. Deploy app and lockfile together, install locked dependencies, build assets, migrate the staging site, run tests, and repeat on production during a maintenance window. Recover failed data migrations by restoring the matched database/files/app version, not by blindly reverting source.

Monitor web error rates and latency, worker queues/failures, scheduler heartbeat, Redis, database storage, backup age and HTTPS expiry. Use Frappe Error Log and Version records without logging credentials or unnecessary personal information. Payment, settlement, notification and GPS monitoring/retention are pending those phases.

## Uninstallation

`bench --site <disposable-site> uninstall-app local_commerce` removes app-owned DocTypes through Frappe. Companies and Users are standard records and must not be deleted by this app. Role fixtures may remain because they can be assigned to Users; reinstall preflight deliberately refuses these ambiguous collisions. Before reinstalling on a disposable site, review and remove retained LC Role assignments and records through Frappe, or use a fresh site. Automated safe role provenance/cleanup and verified reinstall are an outstanding release gate. Never uninstall from production as an upgrade procedure.

## Troubleshooting and references

- Missing assets: run `npm ci` followed by `bench build --app local_commerce`; inspect the Vite manifest and the app asset symlink.
- No shops: verify the user's LC Role and enabled matching membership. Check pagination and that the user can access LC Shop.
- Permission error: do not work around it using `ignore_permissions`; review the membership and requested operation.
- CSRF/session error: sign in again and use the Frappe-served page on the same origin. Do not disable CSRF.
- Install failure: confirm both framework major versions and resolve reported namespace collisions before retrying.

Implementation references: [Frappe v15 app generator](https://github.com/frappe/frappe/blob/version-15/frappe/utils/boilerplate.py), [Frappe hooks](https://docs.frappe.io/framework/user/en/python-api/hooks), [Frappe apps](https://docs.frappe.io/framework/user/en/basics/apps).
