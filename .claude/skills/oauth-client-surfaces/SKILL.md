---
name: oauth-client-surfaces
description: Use for Android or web client-facing authentication and APIs for POS, Mobile Sales, Shopping, or Restaurant across aimatic and Posapplication, including OAuth2 PKCE, device enrollment, refresh tokens, product endpoints, and client/server contract changes.
---

# OAuth client surfaces

aimatic owns server authority; `/home/nabeel/Posapplication` owns product
clients. Read the client repo guide before editing it.

## Gotchas

- Separate public OAuth client per product (POS/Sales/Shopping/Restaurant),
  created by owned patch with exact redirect URIs/scopes. PKCE, no client secret.
- Android POS device proof ≠ cashier OAuth identity. Derive cashier from the
  authenticated session; bind device requests to stored proof hash + POS Profile.
- Refresh-token rotation/replay lives in `aimatic.aimatic.oauth.endpoints`.
  Reuse the shared client refresh path — no hand-built auth headers in features.
- Server derives identity and business context (user/customer/waiter, prices,
  stock, taxes, credit). Reject client-asserted values the server can derive.
- Keep product UI, routes, plugins, OAuth config, and API modules isolated.
  Electron is POS-only. Do not hide one product inside another.
- Each product has its own durable idempotency record and stable request ID.
  Offline replay returns the original server document.
- Changing POS Device `doc_events` needs site cache clear + Gunicorn reload —
  Frappe caches hooks in long-lived workers.
