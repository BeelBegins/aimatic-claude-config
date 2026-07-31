---
name: oauth-client-surfaces
description: Use for Android or web client-facing authentication and APIs for POS, Mobile Sales, Shopping, or Restaurant across aimatic and Posapplication, including OAuth2 PKCE, device enrollment, refresh tokens, product endpoints, and client/server contract changes.
---

# OAuth client surfaces

Inspect both repositories when the contract crosses them: aimatic owns server
authority; `/home/nabeel/Posapplication` owns isolated product clients. Read the
client repository guide before editing it.

## Authentication boundaries

- Keep a separate public OAuth client for POS, Sales, Shopping, and Restaurant.
  Create each through an owned patch with exact redirect URIs and scopes. Public
  clients use Authorization Code with PKCE and never carry a client secret.
- Keep Android POS device proof separate from cashier OAuth identity. Derive the
  cashier from the authenticated session and bind device requests to the stored
  proof hash and assigned POS Profile.
- Preserve refresh-token rotation and replay handling in
  `aimatic.aimatic.oauth.endpoints`. Reuse the centralized client refresh path;
  never hand-build authorization/device headers in feature code.
- Store native credentials only through the secure-storage abstraction. Keep
  browser callbacks and storage restricted to the configured product origin.

## Server authority

Derive identity and business context server-side:

- Sales: user, company, warehouse, salesperson, credit, prices, stock, taxes.
- Shopping: Customer from authenticated `portal_users`; signed quote, stock,
  price, and checkout revalidation from the server.
- Restaurant: waiter, branch, menu/modifier prices, order and kitchen state.
- POS: cashier identity and final pricing/accounting/FBR behavior.

Reject client-asserted values where the server can derive or validate them.

## Product isolation and retries

Keep product UI, routes, native plugins, OAuth configuration, and API modules in
their current product profiles. Electron remains POS-only. Do not hide one
product inside another with roles or CSS, import mock Restaurant data into live
flows, or give Shopping employee/terminal access.

Use the product's own durable idempotency record and stable request ID for every
create/update queue. Do not reuse Sales, Shopping, Restaurant, or POS request
records across products. Offline replay must return the original server document
instead of creating another.

## Verify narrowly

Test the affected product's PKCE/login or endpoint, one permission denial, token
refresh/replay behavior when relevant, and its idempotent retry. Confirm another
product's build/profile remains isolated only when shared authentication or build
configuration changed. Use `posapplication-release` only for build or publication
requests.
