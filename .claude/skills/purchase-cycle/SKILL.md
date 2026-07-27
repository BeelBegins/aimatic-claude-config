---
name: purchase-cycle
description: Use for Purchase Order, Purchase Receipt, Purchase Invoice, purchase returns, supplier pricing, purchase taxes/formulas, trade offers, landed costs, purchase grid behavior, or any Client Script/Server Script fixture that changes procurement behavior.
---

# Purchase cycle

Treat procurement as one connected accounting and stock flow. Trace the full
path before changing a field or formula:

`Purchase Order -> Purchase Receipt/return -> Purchase Invoice/return -> stock, supplier payable, tax and selling-price effects`.

## Invariants

- Server-side validation/calculation is authoritative; client scripts may
  improve entry but must not be the only correctness control.
- Preserve document lifecycle and return semantics (`docstatus`, returned
  quantity, references, stock and GL reversal).
- Never trust client-supplied price/tax/account values when the server can
  derive or validate them.
- Branch, warehouse, cost center, company and supplier context must remain
  aligned; do not restore generic fallbacks.
- Test normal purchase, partial/full return, cancellation, amendment and
  replay/idempotency paths proportionately to the change.
- Shelf/Foodpanda price application is separate from purchase validation.
  Load `shelf-pricing` whenever selling prices are affected.

## Where to inspect

- `apps/aimatic/aimatic/fixtures/client_script.json`
- `apps/aimatic/aimatic/fixtures/server_script.json`
- purchase-related Custom Field and Property Setter fixtures
- purchase hooks/patches in `apps/aimatic/aimatic/`
- `shelf-pricing` for Item Price creation/restoration

The lossless pre-refactor project record remains in
`../../reference/project-knowledge-archive-2026-07-28.md`. Search it for
Purchase Order, Purchase Receipt, return, tax, trade offer, MRP, vendor rate,
and Foodpanda when historical reasoning is needed.

## Safe workflow

1. Inspect local diffs and identify every document/event in the flow.
2. Search fixtures by script `name` and embedded code, not only filenames.
3. Confirm existing standard ERP behavior before adding custom logic.
4. Change the smallest owning layer.
5. Validate fixture JSON and extract/check embedded JS/Python where practical.
6. Use a disposable/local site for behavior tests; no live mutations without
   the production gate.
7. Record durable decisions and known regressions in this skill or a linked
   reference.
