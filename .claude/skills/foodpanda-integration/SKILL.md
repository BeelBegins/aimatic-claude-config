---
name: foodpanda-integration
description: "Use for the Foodpanda Partner API integration: OAuth client-credentials token handling, Foodpanda Settings/Outlet/Product/Category Map/Order Log doctypes, catalog and availability sync, outlet open/closed/busy status, and inbound order webhooks that create Sales Orders."
---

# Foodpanda Partner API integration

Start in `apps/aimatic/aimatic/foodpanda_integration/`: `client.py` handles
OAuth token caching and the generic authenticated HTTP call, `catalog.py`
pushes items/prices/availability, `outlet.py` pushes open/closed/busy status,
`orders.py` + `api.py` receive and process order webhooks. This is separate
from - and reuses - the local Foodpanda Price List mechanism owned by
`shelf-pricing` (`aimatic/shelf_pricing/`), which only maintains ERPNext's own
per-branch Foodpanda selling prices and never calls Foodpanda's API.

## Invariants

- Keep all Foodpanda credentials (`client_id`/`client_secret`/`webhook_secret`)
  in `Foodpanda Settings` `Password` fields, and the per-branch `vendor_id` in
  `Foodpanda Outlet`. Never log a token or secret, put one in a fixture, or
  return one to a client.
- Cache the OAuth access token (`client.get_access_token`), don't fetch a new
  one per call - Foodpanda rate-limits per client ID. Invalidate the cache on
  a `401` rather than assuming the cached token is still good.
- Keep the order-webhook idempotency gate intact: dedupe on
  `Foodpanda Order Log.foodpanda_order_id` before creating a Sales Order, and
  write that log row (status `Received`) before attempting Sales Order
  creation, committed ahead of the creation savepoint - a crash or a rejected
  order must still leave an auditable row, not silently disappear.
- Keep catalog pushes content-hash-gated (`Foodpanda Product.content_hash`) so
  an unchanged item doesn't get re-pushed on every sync trigger.
- A Sales Order built from a webhook stays a draft (docstatus 0), matching
  `aimatic.shopping.api._make_order` - staff review/submit it, this
  integration does not auto-submit.
- Reject insufficient-stock lines rather than oversell; reject the Foodpanda
  order (via `orders.reject_order`) whenever Sales Order creation fails, so
  Foodpanda's side isn't left in limbo.

## Open verification gap

Catalog endpoints/payload fields (`catalog.py`) are confirmed against
developer.foodpanda.com's `catalog-api-use-cases` page: add/update are both
`POST`/`PUT /v2/chains/{chain_id}/vendors/{vendor_id}/catalog`, async (202 +
`job_id`), job status via `GET /v2/chains/{chain_id}/catalog/jobs/{job_id}`
returning `QUEUED`/`IN_PROGRESS`/`COMPLETED`/`FAILED`. The confirmed
update-payload fields are `sku`/`active`/`price`/`barcode`/`quantity`/
`maximum_sales_quantity`; push real stock via `quantity`, not just a boolean.
The create-payload's extra fields (`name`/`description`/`category_id`) are
still a guess - the docs only showed an update example. Order and Outlet
Management endpoint paths/payload shapes (`orders.py`, `outlet.py`) are still
from the earlier, less specific spec summary - not yet checked against
per-section docs the way Catalog was. The webhook signature header
name/scheme and the order accept/reject status enum strings are explicitly
flagged as unconfirmed in `orders.py`. None of this has been exercised
against a live response - there are no Foodpanda credentials on file yet.
Re-verify before relying on it, and update the single named constants each
piece is isolated behind rather than the call sites.

Never call the live or sandbox endpoint without explicit approval and current
credentials, per this repo's safety rules.

## Verify narrowly

Everything here is unit-testable with `requests` mocked - test token
cache hit/miss/expiry and 401-refetch in `client.py`; hash-skip and
create-vs-update branching in `catalog.py`; and, for the webhook, signature
accept/reject, idempotent replay of the same `foodpanda_order_id`, and
insufficient-stock rejection in `orders.py`/`api.py`. Expand to `shelf-pricing`
tests only when the shared price-list helpers also change.
