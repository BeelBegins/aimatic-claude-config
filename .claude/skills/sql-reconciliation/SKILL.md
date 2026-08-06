---
name: sql-reconciliation
description: Use for heavy SQL analytics, drill-through reports, vendor performance, COGS, stock valuation, gross margin, or reconciliation across Stock Ledger Entry, GL Entry, transactions, and source data.
---

# SQL analytics and reconciliation

Shape after current report code (e.g. `vendor_performance/api.py`); verify
schema/semantics in the installed version before writing SQL.

## Gotchas

- Cheap aggregates first; per-item/voucher detail only on explicit drill-through.
  Reset detail when filters change.
- Bound expensive FIFO/ledger replay: count first, return `too_large` above an
  evidence-based threshold.
- Parameterize; use Frappe permission/company/branch scope. No unrestricted SQL.
- COGS is SLE cost-basis (commonly `-stock_value_difference`), not sales revenue
  and not every Stock Entry. Name exceptional correction vouchers explicitly.
- Headers may carry `branch`; SLE/Bin carry `warehouse`. Expand branch → tagged
  warehouses. Define zero-warehouse behavior; never emit empty `IN ()`.
- Older docs may lack `branch` — surface as a completeness caveat.
- Validate totals on an independent path (second aggregate, GL, SLE, or source
  workbook).
- Branch Price Sheet cost map: PR/PI supply explicit excl/incl custom fields;
  Stock Entry `basic_rate` is tax-exclusive — reconstruct display-inclusive via
  Item FBR tax rate. Never treat `valuation_rate` as proof of included GST.
