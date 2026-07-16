---
name: oauth-client-surfaces
description: Working on Mobile Sales, Customer Shopping, Restaurant Waiter, or Android POS device/cashier auth — any OAuth2 PKCE client surface, spanning aimatic's server-side modules (mobile_sales, shopping, restaurant, offline_pos Android auth) and the separate Posapplication client repo (device enrollment, oauth-pkce, credential-provider, products/sales, products/shopping, products/restaurant). Use whenever adding/modifying an Android or web client-facing endpoint, an OAuth client, or these three focused client products.
---

# OAuth client-app surfaces (Android POS, Sales, Shopping, Restaurant)

## Two repos, one feature family

Server side lives in `apps/aimatic` (this bench). Client side lives in a **separate** repo,
`~/Posapplication` (`github.com/BeelBegins/Posapplication`, not part of this bench, own git
history/versioning — currently well past the early "core extraction" groundwork stage; Sales,
Shopping, and Restaurant are real built-out Capacitor products under `src/products/`, not just
prep work). Posapplication has its own `CLAUDE.md` — read it before touching client code; this
bench's `CLAUDE.md` only documents the server side.

## Four separate public OAuth PKCE clients — no client secrets, ever

Each product has its own client, created by its own patch in `apps/aimatic/aimatic/patches/`
(registered in `patches.txt`):

| Product | Patch | Notes |
|---|---|---|
| POS (Android) | `create_pos_oauth_client` | redirect `com.beelbegins.aimaticpos://oauth/callback` |
| Sales | `create_sales_oauth_client` | Capacitor-only, own OAuth client |
| Shopping | `create_shopping_oauth_client` | native redirect `com.beelbegins.aimaticshopping://oauth/callback` **plus** one exact optional HTTPS web callback (`get_public_config` rejects any non-matching browser origin) |
| Restaurant | `create_restaurant_oauth_client` | `restaurant-waiter` scope |

Never give a new client-app product a shared/reused client — each gets its own patch-created
public PKCE client, none with a client secret.

## Two same-named `offline_pos` directories — don't confuse them

- `apps/aimatic/aimatic/offline_pos/` (top-level) — `api.py` (~2300 lines), the main Electron POS
  terminal API surface (cashier login, shift lifecycle, sale/refund). Covered by the separate
  `offline-pos` skill.
- `apps/aimatic/aimatic/aimatic/offline_pos/` (nested one level deeper, under the `aimatic`
  Module Def folder alongside `doctype/`, `print_format/`, `workspace/`) — `device_auth.py`
  (Android device/cashier Bearer auth hook, `validate_android_pos_device_auth`, wired via
  `auth_hooks`) and `device_events.py` (the `POS Device` doc-event hook,
  `on_pos_device_update`). `hooks.py` spells the dotted path out in full:
  `aimatic.aimatic.offline_pos.device_auth` / `...device_events` — the doubled `aimatic.aimatic`
  is correct, not a typo, because of this nesting. Grep the right one before editing.
- Android device/enrollment doctypes (`POS Device`, `POS Device Enrollment`,
  `POS Device Audit Log`) live under `apps/aimatic/aimatic/aimatic/doctype/pos_device*` — same
  nested-module path.
- Frappe caches `doc_events` in long-lived web workers — after changing or deploying anything
  under this nested `offline_pos` path, clear the site cache and gracefully reload Gunicorn, or a
  stale worker keeps calling the old path.

## Shared security invariant across all four — never trust client-asserted identity/price

- **Android POS**: cashier identity is the Bearer-authenticated `frappe.session.user`, never a
  client-supplied `cashier_user`. `X-Aimatic-Device-ID` + `X-Aimatic-Device-Token` are verified
  against a stored proof hash and bind the request to its POS Profile.
- **Mobile Sales** (`aimatic.mobile_sales.api`): user derived from OAuth; never accepts
  client-supplied rates, credit, outstanding, company, warehouse, or salesperson identity as
  authoritative. Item search batches Bin/Item Price reads rather than per-item queries.
- **Shopping** (`aimatic.shopping.api`): Customer identity comes only from
  `Customer.portal_users` linked to the authenticated Website User — never accept a Customer
  identity from the client. Quotes are short-lived HMAC-signed calculations; checkout revalidates
  price/stock server-side regardless of what the quote said.
- **Restaurant** (`aimatic.restaurant.api`): waiter identity, branch context, modifier price
  adjustments, and kitchen ticket status are all server-owned; never accept them from the client.
  Table transfer/merge, split billing, and POS Invoice creation are deferred — don't wire them up
  as a side effect of unrelated work.

When adding a new endpoint to any of these four modules, grep for how the *existing* endpoints in
that same module derive identity/price and match that pattern — don't add a parameter that lets
the client assert something the server should compute.

## Refresh-token security is shared infra across all four clients

`override_whitelisted_methods` routes Frappe's token endpoint to
`aimatic.aimatic.oauth.endpoints.get_token` (nested-module path, same nesting as the
`offline_pos` note above). `AimaticOAuthRequestValidator` rotates refresh tokens on every use;
reuse of an already-rotated token is treated as replay and revokes the affected user/client token
family. This is custom behavior layered on top of Frappe without modifying Frappe core, and it
applies to every one of the four OAuth clients, not just POS — a change here affects Sales/
Shopping/Restaurant token refresh too.

## Idempotency records — one per product, don't reuse another product's

Each client-facing "create an order/ticket" flow has its own dedicated idempotency doctype
mapping a stable client-supplied ID to one server document, so retries/offline-queue replays
don't double-create:
- `Mobile Sales Order Request` → one Sales Order, keyed by client `request_id`.
- `Shopping Order Request` → makes Shopping checkout retries idempotent.
- Restaurant `Kitchen Ticket` records are immutable and request-idempotent for KOT dispatch.

A new product surface needs its own equivalent record — don't repurpose one of these three for a
different product's create-order flow.

## Shopping product-image pipeline stays isolated from the Frappe environment

The System Manager-only `/uploadimageproduct` page (`aimatic.shopping.product_images`) queues
background removal in a **separate** Python 3.12 environment at
`/home/nabeel/.local/share/aimatic-bgremove` — keep ONNX/rembg out of the Frappe environment
itself, and keep the upload route proxied only as an authenticated backend page. It retains the
original image and only updates `Shopping Product.image` after explicit approval.

## Client-side entry points (Posapplication)

Android auth/enrollment: `src/mobile/device-enrollment.ts`, `enrollment-qr-scanner.ts`,
`oauth-pkce.ts`, `capacitor-oauth-browser.ts`, `credential-provider.ts`, `secure-storage.ts`.
`src/api/client.ts` owns auth-mode headers and the single 401 refresh/retry path; `src/core/
auth-fetch.ts` is the shared legacy request adapter. **Do not add raw authorization or
device-proof headers anywhere else** — see Posapplication's own `docs/android-authentication.md`
for the full contract.

Product code: `src/products/sales/` (+ `src/api/sales-orders.ts`), `src/products/shopping/`,
`src/products/restaurant/` (+ `src/api/restaurant.ts`) — each is a separate, isolated Capacitor
build, enforced by `src/config/product-profiles.json`. Never put Restaurant/Sales/Shopping
screens into the Electron POS renderer and hide them with CSS/roles; Electron stays POS-only. See
Posapplication's `docs/product-architecture.md` / `docs/build-profiles.md` for the build-
separation mechanics, and `docs/shopping-preparation.md` / `docs/mobile-sales-phase3.md` /
`docs/restaurant-phase2.md` for each product's own detail.

## Working safely

- Test against each product's own OAuth client — never a shared/reused one.
- Before adding a new client-facing field, default to "server-computed/validated," not
  "client-supplied and trusted" — that's the standing rule across this whole feature family.
- Update the relevant `offline_pos`/`mobile_sales`/`shopping`/`restaurant` section of this
  bench's `CLAUDE.md`, **and** the corresponding section/doc in Posapplication's own `CLAUDE.md`
  or `docs/*.md`, in the same session if this surfaces a new client, endpoint, or security rule —
  these two repos have separate git histories and drift apart easily if only one gets updated.
