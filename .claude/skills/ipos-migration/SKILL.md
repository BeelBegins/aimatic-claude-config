---
name: ipos-migration
description: Use for legacy iPOS item, barcode, price, stock, supplier, vendor-ledger, opening-balance, brand, reference-data, SZL setup, cutover, or re-run work using the tracked migration toolkit.
---

# iPOS migration

Tracked scripts/runbooks live in `apps/aimatic/ipos_data_migration/`. Read
`import.md`, `supplierimport.md`, `customerimport.md`, or `setup_szl.md` for
the phase. Source workbooks may sit in site files; logic stays in Git.

## Gotchas

- Start from the closest current script. Lock site/file/company/warehouse/
  branch/cost center/accounts/posting date with a hard target guard.
- Dry run by default. Live pass needs approval, verified backup, expected
  totals, and rollback.
- Re-runs must find/update intended records — no duplicate Items, barcodes,
  prices, Stock Entries, Suppliers, Contacts, or opening JEs.
- Do not use tax-inclusive source cost as stock valuation; route opening stock
  and supplier balances through configured opening accounts.
- Stamp branch/cost center on rows when hooks do not. Treat any
  `FAILED`/`FAILURE` output as incomplete even if the process exits 0.
- Periodic-commit `rollback()` can silently erase earlier work — verify Bin/GL
  state, not just printed stats.
- Reconcile source counts, unmatched keys, stock/valuation, supplier closings,
  SLE, and GL independently before cutover.
