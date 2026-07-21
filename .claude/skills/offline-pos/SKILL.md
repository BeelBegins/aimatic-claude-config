---
name: offline-pos
description: Electron POS terminal API work in offline_pos/api.py — cashier login, admin/supervisor step-up authorization, POS session/shift lifecycle (Opening/Closing Entry), sale or refund submission, or anything the Posapplication Electron client calls over HTTP.
---

# offline_pos API (Electron POS terminal backend)

`apps/aimatic/aimatic/offline_pos/api.py` (~2300 lines) is the whitelisted surface backing a
separate Electron client repo (`~/Posapplication`, `github.com/BeelBegins/Posapplication`, not
part of this bench). Every endpoint gates on `_require_login`/`allow_guest=False` — the
terminal itself holds its own persistent Frappe session.

## Two distinct identities — don't conflate them

The terminal's Frappe session and a **cashier** are different things. A cashier is a
terminal-scoped identity layered on top of the terminal's own session; logging a cashier
in/out never switches the underlying Frappe session. Any new endpoint needs to be clear about
which identity it's checking.

## Cashier auth

- Verify credentials via Frappe's own `check_password` — never a manual hash compare.
- Role-gated via `_ALLOWED_CASHIER_ROLES = {"POS User", "POS Supervisor", "System Manager"}`.
- Every login attempt (success or failure reason) is audited to `POS Cashier Login Log` via
  `_audit_cashier_login` — password is never logged. Preserve this for any new auth path.

## Admin/supervisor step-up auth — preserve this pattern exactly for new sensitive actions

`authorize_pos_admin_action` → `consume_pos_admin_authorization` (currently gating
`setup_pin`/`reset_pin`/`change_credentials`): HTTPS-only
(`_require_https_for_pos_admin_authorization`), mints a random `secrets.token_urlsafe(32)`
token where **only its SHA-256 hash** is persisted (5-minute expiry), and consumption does a
`SELECT ... FOR UPDATE` on the token row to prevent a double-consumption race — one token
authorizes exactly one action once. Every step is audited to `POS Admin Audit Log`. Any new
sensitive terminal action should extend `_ALLOWED_POS_ADMIN_ACTIONS`, not build a parallel
weaker auth path.

## Session/shift lifecycle

A "session" is an ERPNext `POS Opening Entry`/`POS Closing Entry` pair, looked up **by
`cashier_user`**, never by the terminal's authenticated session user — a terminal is shared
across cashiers, so "my session" isn't meaningful here. If a different cashier already has a
profile's shift open, it surfaces under `other_open_sessions` as diagnostic info only, never
silently reused.

`close_pos_session` must likewise authorize the **human cashier**, not require the fixed terminal
API identity to hold POS Closing Entry DocPerm. It verifies that the cashier owns the Opening
Entry and either has `POS Supervisor`/`System Manager` or supplies a valid single-use
`close_shift` supervisor token, then inserts/submits the Closing Entry with permissions bypassed
inside that controlled RPC only. The bypass on the Closing Entry itself is not enough:
`POSClosingEntry.on_submit` creates a Merge Log and consolidated Sales Invoice whose permissions
are checked independently. After inserting the Closing Entry under the terminal identity,
`close_pos_session` therefore switches to `Administrator` only around `closing.submit()` and
restores the terminal user in `finally`; this also gives >=10-invoice queued consolidation jobs
the correct execution user. Do not restore a leading `frappe.has_permission("POS Closing
Entry", "create")` check against the request session or remove the controlled
`ignore_permissions` flags: production `siezal` terminals intentionally authenticate as
`cashier2/3/4` with POS User only, and that extra transport-identity check blocked both a real
supervisor cashier and the supervisor-token path before their actual authorization was evaluated.
The generic POS Closing Entry Custom DocPerm remains POS-Supervisor-only, so a plain POS User
still cannot create one directly through Desk or `/api/resource`.

## Idempotency

`submit_online_sale`/`submit_pos_refund` key off `terminal_invoice_id`/`terminal_refund_id`
(`_find_existing_invoice`/`_find_existing_return`) — a retried request returns the existing doc
rather than double-submitting. Any new submission-style endpoint needs the same
find-existing-before-insert pattern.

## Shared builder

`_build_pos_invoice_doc` is the **one** place that assembles a POS Invoice from
`(pos_profile, customer, items, ...)`, used by both `preview_cart` (unsaved, never
inserts/submits/touches FBR counts or loyalty ledger) and the real submit paths. Never
duplicate pricing/tax assembly logic outside it — that's exactly how preview and submit would
drift apart.

## Stock/GL timing — expected behavior, not a bug

`POSInvoice.on_submit()` does **not** call `super().on_submit()`, so stock/GL never move on an
individual POS Invoice submit, regardless of its `update_stock` value. They only move when a
`POS Closing Entry` is submitted and consolidates POS Invoices into a real Sales Invoice. A
correctly-flagged POS Invoice sitting in an un-closed shift showing no stock movement is
expected.

## Client-side payment completion (F6) — Electron only, not where gift vouchers apply

The Electron renderer's **F6** key/button ("Pay") opens the Payment dialog
(`completePaymentAllocation`/`openPayment` in `Posapplication/src/renderer/renderer.ts`), which
collects one or more split payment rows and, once fully covered, calls `submit_online_sale` with
`payments: paymentRows.map(...)`. This had a real, since-fixed bug: pre-v2.4.7, pressing F6 to
confirm payment didn't reliably complete and print the sale (fixed in commit "Bump version to
2.4.7: F6 payment confirm now completes and prints the sale") — if a payment-completion report
resurfaces, check this exact flow first, not just the server endpoint.

Current gating, useful context before touching this flow again: `openPayment()` requires a valid
cashier session, blocks if `shiftClosed` is true (a closed shift blocks both F6 and F9 until a
new shift starts), and validates the cart's server-side version before allowing payment to begin.
Once the entered amount fully covers the remaining balance, the dialog deliberately does **not**
auto-submit — it shows "Payment Ready" and requires one more explicit F6/click, specifically so a
mistyped last split-payment leg has a beat to be caught before the sale actually submits.

**Cash tendered and change (v2.7.11+, strengthened in v2.7.12, 2026-07-20)** — cash is the only payment type allowed above
the remaining bill amount. The renderer keeps the full amount the cashier entered in
`paymentRows` and sends it unchanged to `submit_online_sale`; it must not cap cash at the amount
due. `_validate_and_set_payments` records that gross amount in the POS Invoice payment row and
sets `paid_amount` to the gross tendered total, then derives `change_amount = paid_amount -
amount_due`. The client-side `changeDue` is only an immediate UI/provisional-receipt estimate;
the submitted POS Invoice and server-rendered receipt are authoritative. Non-cash rows remain
capped at the remaining bill amount so card/other payments cannot become advances. This contract
is what lets the bottom Tendered/Change block in both POS receipt layouts show the cashier's real
cash received and returned, rather than two copies of the invoice total.

Production incident on Counter 3: v2.7.11 was published, but the till remained on v2.7.10 because
the Electron updater only checked when an administrator manually clicked the Settings button.
Bill `ACC-PSINV-2026-00050` therefore sent/stored 750 against 750 despite the cashier entering
1,000 and expecting 250 change. From v2.7.12, packaged Electron checks on every launch,
background-downloads updates, and displays update-ready notices on the POS screen; installation
remains explicit after finishing the current sale. Online receipt preview also replaces its local
payment/change estimate with `submit_online_sale`'s authoritative `payments`/`change_amount`
response before rendering. Do not diagnose this symptom as a print-template problem until the
invoice's stored payment row and the terminal's installed app version have both been checked.

**F6 (Payment) is a different screen from F7 (Benefits)** — don't conflate them. Loyalty points,
coupon codes, and gift voucher redemption are applied via the separate **Benefits (F7)** dialog,
*before* a cashier ever opens the Payment (F6) dialog — see the `loyalty-gift-voucher` skill for
that flow, including a real 2026-07-16 incident where "Gift Voucher" ended up directly selectable
as an F6 payment mode on production, bypassing F7 entirely — now guarded server-side.

## Native dialog focus loss on Windows — use appConfirm/appAlert, never raw confirm()/alert()

Electron's native `window.confirm()`/`alert()` frequently don't return OS-level foreground focus
to the main window afterward on Windows (a `BrowserWindow.focus()` call alone often can't reclaim
it — Windows restricts `SetForegroundWindow` from background processes), which without a fix
means the cashier has to manually Alt+Tab back in mid-sale. `renderer.ts`'s `appConfirm`/
`appAlert` wrappers exist specifically to paper over this (call the native dialog, then invoke
`focusPosWindow()` via IPC) — **every** confirm/alert call site must go through them, never a raw
`confirm()`/`alert()`; a real incident (2026-07-16) had two call sites (`deleteHeldSaleUi`,
`resumeHeldSale`) still calling `window.confirm()` directly, silently missing the fix.
`main.ts`'s `window:focus-pos` IPC handler itself was also strengthened beyond a bare `.focus()`
— it now restores-if-minimized and briefly toggles `setAlwaysOnTop` first, matching the standard
Electron/Windows workaround for this exact class of focus-stealing bug.

## Cross-reference

If POS administrator/Settings login fails with "HTTPS is required for supervisor
authorization" while cashier login works fine, that's the reverse-proxy header bug covered in
the `bench-ops` skill, not a bug in this module — check `config/nginx.conf` before debugging
this code.

## Raw `/api/resource` reads bypass this module entirely — a real permission gap (2026-07-19)

Not everything the Electron client needs goes through `offline_pos.api`'s whitelisted,
already-permission-checked methods. `Posapplication`'s `core/pos-config.ts`,
`core/catalog-sync.ts`, and `core/sale-refund.ts` call Frappe's **generic REST resource API**
directly (`GET/POST /api/resource/<Doctype>[/<name>]`, via `http.fetchErpResource`/
`fetchPagedList` in `core/http.ts`) for a specific list of master-data doctypes. Those calls are
subject to that doctype's own plain core `DocPerm` — `frappe.has_permission`, no special-casing,
no bypass. This matters because **core ERPNext never expects `POS User`/`POS Supervisor` to need
raw doctype permissions** — its own native Point of Sale ("POS Awesome") page mediates all data
access through server-side RPCs that read with `ignore_permissions`, so those two roles ship with
essentially zero `DocPerm` grants anywhere outside the doctypes this app already patched (POS
Opening/Closing Entry, see above). This Electron client doesn't follow that model — it talks
REST directly — so every doctype below silently 403's for a real cashier account until a
`Custom DocPerm` grant exists.

**Real incident**: a cashier given only `POS User`+`POS Supervisor` could authenticate (Settings
screen's API key/secret fetch succeeded — that's just `frappe.auth.get_logged_user`, permission-
free) but the "Test Login" button then failed to populate the POS Profile dropdown, and once a
profile was picked, failed to show its assigned warehouse/terminal ID (both are just fields on
the `POS Profile` document itself — they were never separately fetched, they simply never arrived
because the whole document read 403'd). Only granting *every* role in the system made it work,
which is what made this a permission problem rather than a client bug. Confirmed root cause via
`python3 -c "json.load(open('.../pos_profile.json'))['permissions']"` against `apps/erpnext`'s
own doctype JSON — `POS Profile` only grants `Accounts Manager`/`Accounts User`, nothing for
`POS User`/`POS Supervisor`.

**Fixed** by tracing every `fetchErpResource`/`fetchPagedList`/direct-`api/resource` call site
across `Posapplication/src/core/*.ts` and `src/api/*.ts` (`grep -rn "api/resource\|fetchErpResource(\|fetchPagedList("`)
and granting `POS User`+`POS Supervisor` **read-only** `Custom DocPerm` on exactly the doctypes
those call sites touch, via the same fixture mechanism as the POS Opening/Closing Entry fix
(`hooks.py`'s `Custom DocPerm` filter, `aimatic/fixtures/custom_docperm.json`):

| Doctype | Why the client reads it | Extra perm |
|---|---|---|
| `POS Profile` | profile dropdown + full profile (warehouse, terminal ID, customer, price list) | |
| `Company` | currency/tax context for `syncPosConfiguration` | |
| `Sales Taxes and Charges Template` | tax rows for `syncPosConfiguration` | |
| `Mode of Payment` | payment method list for `syncPosConfiguration` | |
| `Coupon Code` | coupon validation mid-sale | |
| `Customer` | customer lookup/sync (`syncCustomers`, `loadCustomer`) | + `create` (walk-in registration) |
| `Customer Group` / `Territory` | dropdown options for walk-in customer creation | |
| `Item` / `Item Price` / `Bin` | catalog/pricing/stock sync | |
| `Branch` | `api/branches.ts` | |
| `Print Format` | `findPosInvoicePrintFormat` — picks the receipt template to print | |

`Warehouse` needed **no separate grant** — the assigned warehouse is a field on the `POS Profile`
document itself (`profile.warehouse`), not an independent fetch, so fixing `POS Profile` read
access fixed that symptom too, for free.

Verified against the real `cashier1@aimatic.tech` account (roles `POS User`+`POS Supervisor`
only, the same account used to verify the original POS Opening/Closing Entry fix) two ways: (1)
`frappe.permissions.has_permission(doctype, ptype="read"/"create", user="cashier1@aimatic.tech")`
for all 13 doctypes, via `bench execute` against a temp module; (2) a live HTTPS replication of
the actual Electron sequence against production `siezal` — `frappe.auth.get_logged_user`, then
`GET /api/resource/POS%20Profile?fields=[...]`, then `GET /api/resource/POS%20Profile/<name>` —
using temporary API key/secret credentials generated via `frappe.core.doctype.user.user.generate_keys`
and revoked immediately after (`frappe.client.set_value` clearing `api_key`/`api_secret`), the
same disposable-credential pattern used for verifying the Accounts tools fix. Confirmed the
warehouse and `custom_terminal_id` fields both come back correctly once `POS Profile` read
access exists.

**Before adding any new raw `/api/resource` call to the Electron client**, check whether the
target doctype already has a `Custom DocPerm` grant for `POS User`/`POS Supervisor` here — if
not, either add one (extend the fixture filter + create the grant on every site) or, better,
route the read through a new whitelisted `offline_pos.api` method instead (see below).

## Follow-up done same day: whitelisted RPC endpoints replace the raw REST reads

The `Custom DocPerm` widening above fixed the bug fast (pure data/fixture change, no client
release), but it's the *opposite* of core ERPNext's own POS security model (RPC-mediated,
`ignore_permissions`-scoped reads) — every doctype granted there became readable by `POS
User`/`POS Supervisor` from *anywhere* in Desk, not just through the terminal, with no signal in
the Role Permission Manager that the grant exists specifically to keep POS terminals working.
Built the more robust replacement the same day, mirroring `get_item_barcodes`/
`get_uom_conversions`:

**`aimatic.offline_pos.api`** gained four new whitelisted endpoints, gated by an explicit
`_TERMINAL_MASTER_DATA_DOCTYPES` allowlist constant (the same 13 doctypes from the table above)
plus `_require_login()` — no role check beyond being logged in, matching the existing
`get_item_barcodes`/`get_uom_conversions` convention (the terminal's own authenticated identity
is the gate, not a specific role):

- `get_terminal_resource(doctype, name)` — single-document read, `frappe.get_doc(doctype,
  name).as_dict()`. Replaces `GET /api/resource/<doctype>/<name>`.
- `list_terminal_resources(doctype, fields, filters, limit_start, limit_page_length)` — paged
  list read, `frappe.get_list(..., ignore_permissions=True)`. Replaces `GET
  /api/resource/<doctype>?fields=...`.
- `create_walkin_customer(customer_name, customer_group, territory, mobile_no, email_id,
  tax_id, default_price_list)` — replaces `POST /api/resource/Customer`. Duplicate-mobile
  rejection still comes from `customer_validation.py`'s `Customer.validate` hook, not
  reimplemented here.
- `diagnose_terminal_permissions()` — structured `{results: {doctype: bool}, failures: [...],
  all_ok: bool}` against `frappe.has_permission` (the raw-REST-relevant check, so it still
  reflects reality for a terminal on an older client build that hits `/api/resource` directly).
  Not yet wired into the Settings screen UI — callable today via `bench execute`/direct HTTP for
  diagnosis, a UI button is a future addition if this class of bug recurs.

**`Posapplication` v2.7.7** (`~/Posapplication`, pushed to `main` 2026-07-19 — a real release,
see the `posapplication-release` skill) migrated onto these: `core/http.ts`'s
`fetchErpResource`/`fetchPagedList` now call `get_terminal_resource`/`list_terminal_resources`
instead of building `/api/resource/<doctype>` URLs directly. Because those two functions are the
**shared** low-level helpers, every existing caller (`syncPosConfiguration`, `syncCustomers`,
`loadCustomer`, `getCustomerCreationOptions`, `validateCoupon`, the Item/Item Price/Bin catalog
sync) needed *zero* changes — only `http.ts` itself changed. Three call sites had hand-rolled
their own `/api/resource` URLs instead of using the shared helpers
(`loadAvailablePosProfiles`/`loadPosProfile` in `core/pos-config.ts`,
`findPosInvoicePrintFormat` in `core/sale-refund.ts`) — refactored to route through
`http.fetchPagedList`/`fetchErpResource` too, closing the gap for those three and removing the
duplication at the same time. `createCustomer` (`core/catalog-sync.ts`) now posts to
`create_walkin_customer` instead of raw `/api/resource/Customer`. **No changes to
`renderer.ts`/`preload.ts`/`api/client.ts`** — every exported `core/*.ts` function kept its exact
prior signature and return shape, which is what kept this a low-risk, single-day, same-session
fix instead of a multi-file UI refactor. (`src/api/branches.ts`/`customers.ts`/`items.ts`/
`stock.ts`/`pricing.ts` — thin wrappers around `client.ts`'s `getResource`/`listResources`
directly — were confirmed dead code, imported nowhere, and left untouched.)

Verified before pushing: `npx tsc --noEmit` clean, full existing test suite (`npm test`, 86/86)
still green, and — since `client.ts`'s low-level `getResource`/`listResources` URL-construction
test doesn't exercise `http.ts`'s wrappers — a live end-to-end run of the actual compiled
`dist/core/*.js` (not just source) against production-identical `szl`, driven by a small Node
script (`require`-ing the compiled CommonJS output directly, real `fetch`, a minimal `db` stub)
using a real throwaway `POS User`+`POS Supervisor`-only cashier account: `testApiAuthentication`
→ `loadAvailablePosProfiles` → `loadPosProfile` (warehouse + terminal ID both present) →
`syncCustomers` → `createCustomer`, all passing. This required a web worker restart first (new
Python endpoints aren't visible to the preloaded gunicorn workers otherwise — see the
`bench-ops` skill) since `bench execute` alone can't validate the actual HTTP wire format
(query-string encoding, `frappe.form_dict` kwarg matching, the `{"message": ...}` response
wrapping) the way a real request over the wire does.

**The `Custom DocPerm` grants from the section above are deliberately left in place**, not
reverted — they're now a redundant safety net for any terminal still running a client build
older than v2.7.7 (Electron's auto-updater rolls out over time, not instantly to every device).
Revisit removing them once the fleet is confirmed on v2.7.7+ — not done blindly in the same
session as shipping the client that supersedes them, since that would leave zero fallback for a
terminal that hasn't updated yet. Check `gh release list --repo BeelBegins/Posapplication` /
actual deployed-terminal versions before considering that cleanup.

Update the `offline_pos` section of the top-level `CLAUDE.md` in the same session if endpoints,
the auth flow, or the stock/GL consolidation behavior changes.
