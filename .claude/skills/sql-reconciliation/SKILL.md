---
name: sql-reconciliation
description: Building or extending heavy SQL analytics/reporting features — vendor performance, COGS, stock valuation, gross margin, or any dashboard/report that aggregates Stock Ledger Entry, GL Entry, or transaction history. Use whenever the user asks for a new analysis, drill-through report, or reconciliation of totals against source data.
---

# SQL-heavy analytics/reporting pattern

Reference implementation: `apps/aimatic/aimatic/vendor_performance/api.py`. Follow this
pattern for any new heavy-analytics endpoint rather than inventing a new shape.

## Summary-first, drill-through — never one monolithic call

Split into one cheap, always-loaded summary endpoint (aggregate `SUM`/`COUNT` only, no
per-item rows, no full ledger replay) plus separate on-demand detail endpoints the UI only
fires on explicit user action (a "Load" button). Reset each drill-through section to its
unloaded placeholder state whenever the filters change, so stale data for a different
entity/vendor is never shown. Full per-item/per-transaction breakdowns don't scale to entities
with heavy transaction history — don't compute them on every filter change.

## Guard expensive replays

Before an O(all-time-ledger-rows) computation (e.g. a FIFO stock-ledger replay to attribute
current stock back to purchase origin), do a cheap `COUNT(*)` first. Past a hard row-count
threshold, return a `too_large`-style flag instead of attempting the computation — see
`_MAX_ORIGIN_STOCK_SLE_ROWS` in `vendor_performance/api.py` for the precedent. Raise such a
threshold only after confirming the replay is actually fast enough at that row count.

## COGS / valuation correctness

Cost-of-goods-sold is cost-basis value from Stock Ledger Entry valuation
(`-stock_value_difference`), not retail revenue. Be explicit about `voucher_type` scoping
(e.g. `Sales Invoice`/`POS Invoice` only, not Stock Entry write-offs) — and check for known
historical exceptions before assuming a clean filter covers everything. `vendor_performance`'s
`_HISTORICAL_POS_STOCK_CORRECTION_ENTRIES` is a real precedent: a bounded, explicitly-named
list of one-off backfill Stock Entries that must be included as a second match arm, not a
general "count all Stock Entries" rule (which would wrongly pull in unrelated write-offs).

## Branch/Warehouse scoping

`Sales Invoice`/`POS Invoice`/`Purchase Invoice`/`Purchase Receipt`/`Payment Entry` headers
carry `branch` directly; `Stock Ledger Entry`/`Bin` only carry `warehouse` (no `branch`
column). A Branch filter on the latter must expand to that branch's warehouse list via
`Warehouse.custom_branch` (not `branch_management.get_branch_defaults()`, which only returns 2
fixed fields for doc-defaulting, not the general "all warehouses for this branch" answer). If
a Branch resolves to zero tagged warehouses, fall back to unfiltered rather than a
`WHERE warehouse IN ()` that would silently zero everything.

## Data-quality caveats — surface them, don't silently absorb them

`branch` is inconsistently populated on older documents predating branch enforcement (POS
Invoice is explicitly skipped by `apply_branch_defaults`). A Branch-scoped query on
header-level metrics will under-count older activity that never got a `branch` value — say so
in the result/report rather than presenting scoped numbers as complete.

## JS numeric formatting

Use `format_number()`/`money()`/`percent()` helpers, never raw
`frappe.format(value, {fieldtype: 'Float'/'Currency'})` concatenated into a card/string — that
helper wraps output in `<div style="text-align: right">`, which shows up as literal escaped
HTML text outside a proper grid cell context.

## Before reporting a reconciliation as correct

Cross-check totals against an independent source (source file, GL Entry, or a separately
constructed `SUM` query) to the penny — don't trust a single code path's own output as proof
of correctness, the way the iPOS migration verification did against the source workbook
totals.

Update the relevant `CLAUDE.md` section (currently `vendor_performance/`) in the same session
if this surfaces a new scoping rule, guard threshold, or data-quality caveat.
