---
name: foodpanda-integration
description: "Use for the Foodpanda Partner API integration: OAuth client-credentials token handling, Foodpanda Settings/Outlet/Product/Category Map/Order Log doctypes, catalog and availability sync, outlet open/closed/busy status, and inbound order webhooks that create Sales Orders."
---

# Foodpanda Partner API integration

Start in `apps/aimatic/aimatic/foodpanda_integration/`: `client.py` handles
OAuth token caching and the generic authenticated HTTP call, `catalog.py`
pushes items/prices/availability, `outlet.py` pushes open/closed/busy status,
`catalog_jobs.py` applies async assortment callbacks, `webhooks.py` verifies
the portal's static Authorization value, and `orders.py` + `api.py` receive
and process order webhooks. This is separate
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
- Keep `Foodpanda Catalog Job` persistent and callback-driven. Promote
  `pending_content_hash` only after a successful job callback; item-level
  feedback can fail one SKU even when the overall job completed.
- A Sales Order built from a webhook stays a draft (docstatus 0), matching
  `aimatic.shopping.api._make_order` - staff review/submit it, this
  integration does not auto-submit.
- Reject insufficient-stock lines rather than oversell; reject the Foodpanda
  order (via `orders.reject_order`) whenever Sales Order creation fails, so
  Foodpanda's side isn't left in limbo.

## Partner API contract

- Use only `https://foodpanda.partner.deliveryhero.io`; Foodpanda catalog
  testing uses a designated live test vendor, not a catalog sandbox hostname.
- OAuth is form-encoded client credentials at `/v2/oauth/token`.
- Add products with `POST /v2/chains/{chain_id}/catalog`, including top-level
  `vendors` and `products`; localized titles/descriptions and category/barcode
  values use the documented object/array shapes. Product creation is beta and
  remains gated by `allow_product_creation`.
- Update products with `PUT /v2/chains/{chain_id}/vendors/{vendor_id}/catalog`.
  Retrieve catalog/categories and request exports through their vendor paths.
- Configure the assortment callback to `api.foodpanda_catalog_webhook` and
  order callback to `api.foodpanda_order_webhook`. WebhookKeyAuth is an exact
  static `Authorization` value (opaque or full Basic value), not a body HMAC.
- A successful 2xx order webhook acknowledges receipt; never send the
  unsupported `ACCEPTED` status. Outbound statuses are `CANCELLED`,
  `READY_FOR_PICKUP`, and `DISPATCHED` as appropriate.
- Outlet UI `Busy` maps to `CLOSED_UNTIL` with a busy reason and timestamp;
  `Closed` maps to `CLOSED_TODAY`.

Never call the Partner endpoint without explicit approval and current
credentials, per this repo's safety rules.

## Verify narrowly

Everything here is unit-testable with `requests` mocked - test token
cache hit/miss/expiry and 401-refetch in `client.py`; hash-skip and
create-vs-update branching in `catalog.py`; and, for webhooks, static
authorization, job-callback idempotency, item-level feedback, idempotent order
replay, nested client vendor mapping, and insufficient-stock rejection in
`orders.py`/`api.py`. Expand to `shelf-pricing`
tests only when the shared price-list helpers also change.
