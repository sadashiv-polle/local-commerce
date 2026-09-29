# SQL injection review — 29 September 2026

## Result

No confirmed SQL injection vulnerability was found in the Local Commerce source reviewed at commit `5648962`. This is a source review with local regression tests, not a certification that the deployed server is vulnerability-free.

## Scope and evidence

Reviewed all 84 direct `sql` / `sql_list` call sites across 22 production Python files, including search, orders, inventory, reports, scheduled delivery, customer addresses, Cashfree, Manual UPI, and migrations. Also examined ORM field/sort construction, permission-query conditions and the API wrappers for the dynamic listing paths.

- Raw-query input values are supplied separately through placeholders. Search terms, shop/order identifiers, dates and pagination values are not concatenated into SQL statements.
- Admin listing table names, column names and sorting expressions come from a fixed server-side section mapping. Unsupported sections are rejected; platform authorization runs before queries.
- Customer order search constructs conditions from fixed strings, binds values and scopes results to the current customer. SQL-looking product names remain literal search terms.
- Home discovery and inventory `IN` lists generate placeholders only. Stored shop/item names are still passed as parameters, addressing the possibility of SQL-looking text previously saved in the database.
- Inventory field names are selected from a fixed source-code list. Migration table/field substitutions use fixed tuples, not request inputs.
- Permission hooks that must return SQL fragments use `frappe.db.escape` for user and shop values. These rely on the installed Frappe/database driver's escaping implementation.
- Inspected ORM queries use fixed DocTypes/columns and filter values, rather than user-supplied SQL, sorting or projection expressions.

## Regression checks

Added tests for boolean/comment, stacked-statement-looking and UNION/time-delay-looking inputs, admin section and pagination rejection, authorization before SQL, stored inventory/shop identifiers and literal matching of SQL-looking product names. These payloads are used only in local fixtures/mocks; no attack traffic was sent to the live site.

The customer-order tests execute query logic against an isolated SQLite database with parameter placeholders adapted for SQLite. Other added tests inspect the SQL template and separately bound arguments at the database-call boundary. They do not test the production MariaDB driver or server.

Validation: all 202 backend tests passed, and lint passed for the changed tests. No application/runtime code or payment data was changed by this review.

## Limits

The production site's deployed code, Frappe/ERPNext internals, other installed apps, Server Scripts, database settings and reverse-proxy configuration were not inspected. This review does not establish protection against other vulnerability classes such as authorization flaws, XSS, CSRF, dependency vulnerabilities or denial of service. A staging integration assessment would be needed to extend the result to the installed system.

Some existing admin/catalog searches allow SQL LIKE wildcards (`%` and `_`). They may broaden matching within the authorized scope, but because their values remain parameterized this is not SQL injection. Customer order and home shop search escape these wildcards for literal matching.
