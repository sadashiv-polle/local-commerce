# Foundation API

All methods use `/api/method/local_commerce.api.<module>.<method>` and require an authenticated Frappe session. No custom method allows Guest. Responses use the standard Frappe `message` envelope. Mutations require POST and normal Frappe CSRF validation. Do not turn off CSRF in site configuration.

| Method | Verb | Input | Authorization / result |
| --- | --- | --- | --- |
| `session.context` | GET | None | Current user, LC roles, enabled role-matched memberships with authoritative Company, platform flag and session CSRF token |
| `shops.list_shops` | GET | `start=0`, `page_length=20` (max 100) | Frappe list permissions plus LC shop query scope; shop name, ID, Company and status |
| `shops.get_shop` | GET | `shop` | Role + enabled membership, then Frappe document read permission; scoped shop details |
| `shops.update_shop` | POST | `shop`, `shop_name`, `status`, optional `description` | Platform administrator or member Owner; Company cannot be supplied; normal save validation and Version audit |

Memberships are administered in Desk through `LC Shop Member` by an LC Platform Administrator. Standard Frappe resource endpoints for both LC DocTypes remain subject to DocType permissions, query/document hooks and controller validation. IDs are selectors, never authority. Permission policy queries use a caller's actual session identity; escaped shop IDs in query hooks originate from database membership records.

No customer catalog, delivery, inventory, payment, settlement, provider, reporting or realtime API exists in this foundation. Driver membership is recorded for later delivery authorization but grants no shop-management access. The empty capabilities list deliberately advertises no unimplemented operations.


## Owner inventory API

`local_commerce.api.owner` provides GET `catalog`, `detail`, `setup_options`,
`history`, and POST `configure`, `update_product`, `upload_product_image`,
`adjust_stock`. Every method
validates shop membership; mutations require owner/platform authority. Product
selectors must belong to the authorized shop. `adjust_stock` requires
`request_key`, `action` (Add/Remove), `quantity`, `reason`, and positive `unit_cost`
for Add. Warehouse, Company and posting accounts come from validated shop setup.
`update_product` requires the product's returned `modified` value for stale-edit
protection. See `docs/owner-inventory.md` for the full contract and limitations.
