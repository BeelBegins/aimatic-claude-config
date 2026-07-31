---
name: sql-reconciliation
description: Use for heavy SQL analytics, drill-through reports, vendor performance, COGS, stock valuation, gross margin, or reconciliation across Stock Ledger Entry, GL Entry, transactions, and source data.
---

# SQL analytics and reconciliation

Use current report code such as `aimatic/vendor_performance/api.py` as a shape,
then verify schema and semantics in the installed version before writing SQL.

## Query design

- Return cheap aggregate summaries first. Load per-item, per-voucher, or
  per-transaction detail only on explicit drill-through and reset it when
  filters change.
- Bound date ranges, rows, groups, and expensive replay work. Before a FIFO or
  all-ledger replay, count candidate rows and return a clear `too_large` result
  above an evidence-based threshold.
- Parameterize values and use Frappe permission/company/branch scope. Do not
  expose unrestricted SQL or interpolate user input.
- State the document statuses and voucher types included. COGS is cost-basis
  value from the correct Stock Ledger valuation source, commonly negative
  `stock_value_difference`, not sales revenue and not every Stock Entry.
- Keep exceptional correction vouchers bounded and explicitly named in code;
  never broaden a one-off rule to all vouchers of that type.

## Scope correctly

Header transactions may carry `branch`; Stock Ledger Entry and Bin carry
`warehouse`. Expand branch filters for stock data through warehouses tagged to
that branch. Define explicitly what zero matching warehouses means; never emit an
invalid empty `IN` clause or silently claim complete zero activity. Surface older
documents with missing branch values as a completeness caveat.

## Reconcile independently

Validate totals against a second path that does not reuse the implementation:
a separately constructed aggregate, GL Entry, Stock Ledger Entry, or the source
workbook. Reconcile currency to the smallest unit and explain differences by
document/status/scope. Test one bounded summary and one drill-through; expand only
when a mismatch points to a specific ledger or filter path.
