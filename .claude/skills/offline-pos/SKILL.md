---
name: offline-pos
description: "Use for the Electron POS terminal backend in aimatic.offline_pos: cashier login, supervisor step-up, shifts, sales/refunds, payments, terminal permissions, retries, or any HTTP contract used by the Posapplication Electron client."
---

# Electron POS backend

Primary code: `aimatic/offline_pos/api.py`. Check Posapplication callers before
changing a contract.

## Gotchas

- Terminal Frappe session ≠ human cashier. Cashier login must not switch the
  transport session. State which identity each endpoint authorizes.
- Passwords via Frappe's `check_password`; audit logins without logging secrets.
- Sensitive actions use the existing step-up flow: HTTPS, short expiry,
  hash-only token, action binding, single-use under row lock, audit. No parallel
  PIN/reusable-token bypass.
- `void_item`, `clear_cart`, and `refund` are distinct action-bound step-ups.
  Do not reuse tokens across them. Supervisors/System Managers keep the
  `can_void_items` / `can_refund` bypass. Cart actions (`void_item`,
  `clear_cart`) are client-consumed; `refund` and `close_shift` consume the
  token inside the server submit so a failed/rolled-back action does not burn
  authorization.
- Shifts resolve by `cashier_user`, not the terminal API user. Same for
  `preview_cart` on Electron — never regress preview to the terminal account.
  Android Bearer derives cashier server-side.
- Shared `_build_pos_invoice_doc` for preview and submit so pricing cannot drift.
  Idempotent on `terminal_invoice_id` / `terminal_refund_id`.
- POS Invoice stock/GL post only via consolidated Sales Invoice at shift close —
  not per invoice submit.
- Prefer allowlisted RPCs over broadening Custom DocPerm or generic
  `/api/resource`. Existing DocPerm grants are compatibility for older terminals.
- Reject server-only payment modes (e.g. Gift Voucher) from client payment rows.
- Food Panda Credit uses a zero-amount payment marker so the receivable stays
  outstanding. ERPNext's `clear_unallocated_mode_of_payments` deletes amount=0
  rows on submit — `offline_pos.events.restore_food_panda_credit_payment_marker`
  must keep that marker for shift consolidation. Do not "fix" credit sales by
  setting the marker amount to the grand total.
- A Failed POS Closing leaves the Opening Entry Open. `_reject_if_failed_closing`
  blocks preview/sale/refund until Close Shift retries successfully. Do not
  allow selling into a stuck Failed close.
- POS barcode lookup is case-insensitive (`s5` == `S5`). Scanner wedge capture
  must accept printable ASCII (including `()`), not only `[A-Za-z0-9\-_.]`.
