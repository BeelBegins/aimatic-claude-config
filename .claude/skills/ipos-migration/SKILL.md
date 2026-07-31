---
name: ipos-migration
description: Use for legacy iPOS item, barcode, price, stock, supplier, vendor-ledger, opening-balance, brand, reference-data, SZL setup, cutover, or re-run work using the tracked migration toolkit.
---

# iPOS migration

Use the current scripts and runbooks under
`apps/aimatic/ipos_data_migration/`. Read `import.md`, `supplierimport.md`, or
`setup_szl.md` for the requested phase. Keep executable scripts there; source
workbooks may live in site file storage, but migration logic must remain tracked.

## Prepare safely

1. Verify the target site's current role and the exact source workbook.
2. Start from the closest current script; do not rebuild settled mappings from
   memory or copy an older narrative.
3. Lock every target constant before execution: site, file path, company,
   warehouse, branch, cost center, accounts, and posting date. Add a hard target
   guard so a script cannot run against another site accidentally.
4. Keep dry run enabled by default. Parse and summarize counts without
   `insert`, `submit`, commit, or destructive cleanup.
5. Before any live pass, obtain explicit approval, take and verify a current
   backup, define expected totals/checks, and prepare rollback.

## Preserve accounting and retry safety

- Keep source-to-target keys stable. Re-runs must find or update the intended
  record rather than duplicate Items, barcodes, Item Prices, Stock Entries,
  Suppliers, Contacts, or opening Journal Entries.
- Follow mapping and valuation formulas in the current runbook and script. In
  particular, do not use tax-inclusive source cost as stock valuation, and route
  opening stock and supplier balances through the configured opening accounts.
- Stamp branch and cost center on transaction rows where hooks do not supply
  them. Reject ambiguous company/branch resolution.
- Collect row failures visibly and treat any `FAILED`/`FAILURE` output as an
  incomplete run even when the process exits successfully.
- Never delete submitted or ledger-linked partial results casually. Inspect SLE,
  GL, Item Price, and document references; prefer cancellation and an explicit
  repair plan.

## Reconcile every pass

Compare source row/group counts, unmatched keys, barcode and master counts,
opening quantities and valuation, supplier closing balances, Stock Entry totals,
Journal Entries, GL Entry, and Stock Ledger Entry independently. Reconcile money
to the smallest currency unit and explain every residual before cutover. Expand
checks only where a mismatch identifies a specific mapping or ledger path.
