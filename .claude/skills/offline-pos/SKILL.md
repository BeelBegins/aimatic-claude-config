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

### Suggested follow-up, not yet done: stop widening raw doctype permissions

The `Custom DocPerm` approach fixes the bug with minimal code (pure data/fixture change, no
client release needed) and is consistent with the existing POS Opening/Closing Entry precedent,
but it has a real downside worth flagging: it's the *opposite* of core ERPNext's own POS
security model (RPC-mediated, `ignore_permissions`-scoped reads) — every doctype granted here is
now readable by `POS User`/`POS Supervisor` from *anywhere* in Desk, not just through the
terminal, and a future admin looking at the Role Permission Manager has no obvious signal these
grants exist specifically to keep POS terminals working (unlike a whitelisted Python method,
which is self-documenting and reviewable in one file). A more robust design, mirroring how
`get_item_barcodes`/`get_uom_conversions` already work: add purpose-built whitelisted
`offline_pos.api` endpoints (e.g. `get_pos_profile_bootstrap`, `get_master_data_lookup`) that
read with `ignore_permissions=True` internally, scoped to exactly the fields the terminal needs,
and migrate the Electron client's `fetchErpResource`/`fetchPagedList` call sites onto them one at
a time. That would let `POS User`/`POS Supervisor`'s *generic* Desk permissions stay minimal
again, with the terminal's actual data needs centralized and auditable in this one file instead
of scattered across doctype-level Role Permission Manager entries. Not done as part of this fix —
would require a Posapplication client release, more risk for the same immediate outcome — but
worth doing if this doctype list keeps growing.

A second, cheaper follow-up: add a whitelisted `offline_pos.api.diagnose_terminal_permissions()`
that a supervisor could call from the Settings screen to get a structured pass/fail list against
exactly this doctype matrix, instead of the generic "POS Profile load failed" error the client
currently shows — would have surfaced this bug immediately as "POS Profile: FAIL, Customer: FAIL"
rather than requiring trial-and-error role assignment to diagnose.

Update the `offline_pos` section of the top-level `CLAUDE.md` in the same session if endpoints,
the auth flow, or the stock/GL consolidation behavior changes.
