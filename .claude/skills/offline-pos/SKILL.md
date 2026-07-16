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

Update the `offline_pos` section of the top-level `CLAUDE.md` in the same session if endpoints,
the auth flow, or the stock/GL consolidation behavior changes.
