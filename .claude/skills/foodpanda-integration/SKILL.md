---
name: foodpanda-integration
description: "Use for the Foodpanda Partner API integration: OAuth client-credentials token handling, Foodpanda Settings/Outlet/Product/Category Map/Order Log doctypes, catalog and availability sync, outlet open/closed/busy status, and inbound order webhooks that create Sales Orders."
---

# Foodpanda Partner API

Code: `aimatic/foodpanda_integration/` (`client`, `catalog`, `outlet`,
`catalog_jobs`, `webhooks`, `orders`, `api`). Local branch Foodpanda Price Lists
are owned by `shelf-pricing` and never call this API.

## Gotchas

- Credentials in `Foodpanda Settings` Password fields; `vendor_id` on
  `Foodpanda Outlet`. Never log/fixture/return secrets.
- Cache OAuth tokens; invalidate on `401`. Foodpanda rate-limits per client ID.
- Order webhook: write `Foodpanda Order Log` (`Received`) and commit before the
  Sales Order savepoint. Dedupe on `foodpanda_order_id`. Failed creation must
  still leave an auditable log and reject the Foodpanda order.
- Catalog pushes are content-hash gated. Promote `pending_content_hash` only
  after a successful job callback; item-level feedback can fail one SKU.
- Existing-catalog sync matches Items by **barcode**, never Item Code. Map via
  `map_remote_catalog_by_barcode`, then PUT price/stock using the mapped
  Foodpanda catalog SKU. New induction stays out of that path.
- Webhook Sales Orders stay draft. Reject insufficient-stock lines.
- Host is `https://foodpanda.partner.deliveryhero.io` (live test vendor, no
  catalog sandbox host). WebhookKeyAuth is a static `Authorization` value, not
  body HMAC. Do not send unsupported `ACCEPTED` status.
- Without Partner credentials, use Branch Price Sheet CSV/Excel as the local
  portal fallback — that path is ERPNext price-list maintenance only, not a
  Partner sync.
