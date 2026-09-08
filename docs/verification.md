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
