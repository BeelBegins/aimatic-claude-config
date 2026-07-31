---
name: offline-pos
description: "Use for the Electron POS terminal backend in aimatic.offline_pos: cashier login, supervisor step-up, shifts, sales/refunds, payments, terminal permissions, retries, or any HTTP contract used by the Posapplication Electron client."
---

# Electron POS backend

Work primarily in `apps/aimatic/aimatic/offline_pos/api.py`; inspect current
callers in `/home/nabeel/Posapplication` before changing a contract.

## Preserve identity and authorization

- Keep the persistent Frappe terminal session distinct from the human cashier.
  Cashier login/logout must not switch the transport session. State explicitly
  which identity each endpoint authorizes.
- Verify passwords through Frappe and retain cashier login auditing without
  logging credentials.
- Extend the existing admin-action step-up flow for sensitive actions. Preserve
  HTTPS enforcement, short expiry, hash-only token storage, action binding,
  single-use consumption under row lock, and audit logging. Do not create a
  parallel PIN or reusable-token bypass.
- Resolve opening and closing shifts by `cashier_user`, not by the terminal
  session user. Verify opening-entry ownership and supervisor authorization
  before the narrow controlled permission bypass used to submit a closing.

## Preserve transaction authority

- Keep ERPNext authoritative for customer, prices, taxes, stock, GL, FBR,
  loyalty, vouchers, payments, and final invoice values. Reuse the shared POS
  invoice builder so preview and submit cannot drift.
- Keep `terminal_invoice_id` and `terminal_refund_id` find-before-insert
  idempotency. Return the existing document on a retry; apply the same pattern to
  every new submission endpoint.
- Remember that POS Invoice stock and GL effects are consolidated at POS Closing
  Entry. Do not add per-invoice posting as an incidental fix.
- Reject server-only payment modes such as Gift Voucher from client-supplied
  payment rows even if a POS Profile is misconfigured.

## Govern data access

Prefer explicit whitelisted RPCs with `_require_login`, narrow doctype
allowlists, server-side filters, and stable response shapes. Do not add generic
`/api/resource` access or broaden Custom DocPerm merely for client convenience.
Treat existing narrow grants as compatibility for older terminals until fleet
versions are verified.

## Verify narrowly

Trace the affected client call and server helper, then test the changed auth,
shift, payment, retry, or submission path plus one denied/replayed case. Run
static checks first; expand to broader POS tests only after a failure or when the
change crosses pricing, accounting, FBR, or offline boundaries. Never use a live
sale or shift as a test without the production gate.
