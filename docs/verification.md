# Verification — foundation milestone, 2026-09-08

Environment: empty macOS workspace at start; Python 3.13.5, Node 22.15.0, npm 10.9.2. `command -v bench` returned no executable. No Frappe/ERPNext installation or test site is available here.

## Executed successfully

| Command | Result |
| --- | --- |
| `python3 -m unittest discover -s tests -v` | 9 policy tests passed |
| `npm test` | 3 API-client tests passed |
| `.venv/bin/ruff check .` | All checks passed |
| `.venv/bin/ruff format --check .` | Formatted Python sources passed |
| `python3 -m compileall -q local_commerce` | Success |
| `npm run lint` | Success |
| `npm run build` | Vite production build succeeded; 25 modules; hashed JS/CSS and manifest generated |
| `.venv/bin/python -m build` | Source distribution and Python wheel built successfully |
| `git init -b main` | App root initialized as a Git repository; no commit or remote publication |

The sandbox blocked initial npm/Python registry access. Dependency installation and isolated package build succeeded with approved network access. `package-lock.json` is the single repository lockfile. Generated assets, distributions, virtual environment and node_modules are ignored.

## Not run — Bench and test site unavailable

- `bench new-app local_commerce`: scaffold was reproduced using the Frappe v15 generator's layout instead.
- `bench --site <test-site> install-app local_commerce`
- `bench --site <test-site> migrate`
- `bench build --app local_commerce` (direct Vite build passed, but this is not equivalent)
- `bench --site <test-site> run-tests --app local_commerce`
- Fresh-site installation without manual edits.
- `bench --site <test-site> uninstall-app local_commerce` and reinstall.
- Browser/HTTP authentication, session expiry, CSRF and Frappe resource endpoint tests.

The nine committed Frappe integration tests have not run. Local policy tests do not prove the complete permission engine or database lifecycle. No production deployment, provider sandbox test, accounting reconciliation, backup restore or visual browser verification has been performed. Production readiness and the full master specification remain outstanding.

## Server installation follow-up — Role fixture import

The user supplied a Frappe/ERPNext 15.109.0 installation traceback: DocType sync
completed, then fixture import failed with `KeyError: 'name'`. Every Role fixture
now includes its explicit document `name`, matching `role_name`. A regression test
checks the import identifiers, uniqueness and agreement with permission roles.
All 10 local Python tests and Ruff lint/format checks pass after the fix.

Frappe v15 registers the app in installed_apps before importing fixtures. For this
failure, first confirm `bench --site mysite list-apps` includes local_commerce,
then pull the fix and run `bench --site mysite migrate` to synchronize fixtures.
Do not force-install, uninstall, or remove existing DocTypes to recover. If the
app is absent from list-apps, inspect the site state before retrying installation.
The recovery migration has not yet been verified on the user's server.

## Server follow-up — blank workspace page

Corrected `www/local-commerce.py` to `www/local_commerce.py`: Frappe v15's
TemplatePage replaces hyphens with underscores when discovering Python page
controllers. The old filename left the template without its asset URLs or page
session check. The public route remains `/local-commerce`.
Added local controller-discovery regression coverage and a Bench integration
test exercising TemplatePage's actual discovery. All 11 local tests and Ruff
checks pass; the new Bench test has not run here. Pull the fix and clear the
site website cache while the development Bench is running, then reload the page.

## Dedicated Vue interface

Added responsive customer/store and owner/shop hash routes within the same Vue
application and replaced the ERPNext website wrapper with a standalone document.
Existing owner APIs and permission checks remain in use. Customer categories are
presentation-only and shopping is explicitly unavailable pending its backend.
Vue lint and production build passed, along with 3 client tests and 11 Python
regression tests. Browser visual checks and server verification remain pending.

## Owner product creation milestone

Added a narrow ERPNext Item creation/list/options service and owner Vue product
form. Added Item.lc_shop through the install/migrate Custom Field mechanism and
Item permission/controller hooks. No new DocType or financial/stock mutation.
Seven new Bench tests cover tenant creation, cross-shop APIs and Item permissions,
staff, revocation, immutable ownership, direct-write denial and invalid taxonomy.
These tests require Frappe/ERPNext and have not run locally. Existing 11 local
Python tests and 3 client tests pass; Ruff, Vue lint and production build pass.
Server migration and API verification are still required before relying on this
feature in production.
