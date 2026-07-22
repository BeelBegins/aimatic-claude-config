---
name: ipos-migration
description: Legacy iPOS data migration — importing item/barcode/price/stock or supplier/vendor-ledger data from the old iPOS software into ERPNext for a new site or a re-run (itemasterX.xlsx, vendordataX.xlsx, schema.xlsx style workbooks). Use whenever the user mentions iPOS migration, legacy item import, legacy supplier import, or a new site's data cutover.
---

# iPOS legacy data migration

The entire toolkit — mapping docs and executable per-site scripts — lives in
`apps/aimatic/ipos_data_migration/`. Never write a migration script into a site's
`private/files/`; that directory isn't git-tracked and scatters migration knowledge
outside the one repo that owns it.

## Before touching anything

1. Read `apps/aimatic/ipos_data_migration/import.md` (items) and/or `supplierimport.md`
   (suppliers) in full. These are canonical mapping *decisions*, not background reading —
   don't re-derive a mapping rule that's already settled there.
2. Identify the source workbook's actual location on the target site
   (`sites/<site>/public/files/...` or `private/files/...`) — the script's `FILE_PATH`
   constant points there, but the script itself belongs in `ipos_data_migration/`.
3. Copy the most complete existing per-site script as your starting point, not a blank
   file — `import_siezal_items.py` / `import_siezal_suppliers.py` are currently the most
   complete reference (Item Group tree with majority-vote merges, MRP fallback chain,
   `Exempt` WHT naming, Contact mapping). Save the copy as
   `import_<site>_items.py` / `import_<site>_suppliers.py` in the same directory.
4. Adjust the constants block at the top: `FILE_PATH`, warehouse/company/branch target,
   `POSTING_DATE` (must be set explicitly for a real cutover, not left to default).

## Known mapping rules (don't re-derive — already decided)

**Items:**
- `ItemCode` and `RefCode` are the first two barcodes.
- **`CurCost` is tax-inclusive — always reverse-calculate before using it as a Stock Entry
  valuation rate, never use it raw.** Bug fixed 2026-07-16: both reference scripts used to pass
  `CurCost` straight through as `basic_rate`/`valuation_rate`, inflating imported stock's cost
  basis by the embedded tax — this flowed into COGS once that stock sold, with no matching
  inflation on the (tax-exclusive) Sales side, and was the confirmed root cause of `siezal`
  reporting COGS higher than Sales. Fix: `sales_tax = CurCost * tax_rate / (100 + tax_rate)`,
  `rate = CurCost - sales_tax` — the *exact same formula* `fbr_pos/tax_calculator.py`'s
  `calculate_fbr_item` already uses for the sales-side reverse calculation, using the item's own
  `custom_fbr_tax_category` rate (set during `create_item`, before stock rows are captured — the
  category is already committed by the time the rate is read). Exempt items pass through
  unchanged. **Known caveat**: a row with a blank/invalid `Fbr_Tax_Category` in the source file
  resolves `tax_rate` to `0`, so `CurCost` passes through unfixed for that item — check the
  source file's category fill rate before a new import rather than trusting this blindly. This
  fix is **not retroactive** — `siezal`'s and `hsm`'s already-imported stock still carries the
  original tax-inclusive valuation; correcting historical Stock Ledger Entries is a separate,
  explicit decision.
- `Pcs` UOM needs `Must be Whole Number = No` if source `Onhand` has decimals — set this
  *before* running stock entries, or `UOMMustBeIntegerError` aborts mid-batch.
- MRP fallback chain: source `MRP` if nonzero → else `rp × 1.18` if `rp` nonzero → else
  leave source value as-is.
- Item Group tree: majority-vote parent resolution for subcategories with conflicting
  parents; watch for spreadsheet footer/totals rows (blank `ItemCode`+`Description` but
  a formula string like `=SUBTOTAL(...)` in one cell) — skip these explicitly or they
  create a phantom Item on every re-run.
- Follow-up AI catalogue brand files use `ItemCode` as a **barcode**, not ERPNext's
  `Item.item_code`: join it to `Item Barcode.barcode` and take `AiBrand`. Skip blank/
  `Generic` brands, codes shorter than 8 characters, and unmatched barcodes. Normalize
  case/space/punctuation-only spelling variants before voting; use a strict majority
  when one Item has competing real brands and leave equal-count ties blank for review.
  Create missing Brand masters, hard-guard the target site, keep `DRY_RUN = True` by
  default, and take a backup before the live pass. The SIEZAL implementation is
  `update_siezal_item_brands.py`; its 2026-07-23 live pass assigned 7,318 Items and
  created 831 Brand masters, while leaving 40 tied conflicts untouched.
- Zero-valuation stock entry rows need `allow_zero_valuation_rate` set conditionally
  (`rate <= 0` only), never blanket.
- **Opening-stock GL posting must route through `Temporary Opening`, not `Stock Adjustment`**
  (fixed 2026-07-23). Every Stock Entry row's `expense_account` must be set explicitly to the
  site's `Temporary Opening` account (Asset/Balance Sheet, same suspense account the supplier
  opening-balance Journal Entries already use) — left unset it defaults to
  `Company.stock_adjustment_account`, an Expense/P&L account, which books the entire one-time
  opening-stock value as phantom P&L income for whatever period the migration runs in. Confirmed
  live on `siezal`: Rs 47.1M of opening stock had been credited to `5119 - Stock Adjustment - SSM`.
  After both item and supplier imports are done, run `close_migration_opening_balance.py` once to
  close `Temporary Opening`'s residual to `Opening Balance Equity` — that residual is the site's
  real opening equity contribution/drawdown, by construction, once both migration halves share one
  suspense account. Not retroactive to `szl`/`siezal`/`hsm`. See `import.md`'s "Opening-stock GL
  posting" section.
- **Journal Entry has zero `branch_management` hook coverage** (fixed 2026-07-23) — Sales/Purchase/
  Stock Entry all get `branch`/`cost_center` force-filled by `apply_branch_defaults`, but Journal
  Entry doesn't, so nothing populates `Journal Entry Account.branch`/`cost_center` unless the
  migration script sets it itself. Both `import_siezal_suppliers.py`'s opening-balance JEs and
  `close_migration_opening_balance.py`'s closing JE now call `resolve_company_branch(company)`
  (requires exactly one Branch for the company — throws otherwise, since legacy vendor-ledger rows
  carry no branch/location column to split on) and stamp `branch`+`cost_center` on every account
  line. Confirmed live on `siezal`: `cost_center` on the 1,124 legacy JE lines was correct only by
  coincidence (Company default matched the site's one Branch); `branch` was blank on all of them.

**Suppliers:**
- Group legacy rows by `StandardNTN`, not raw `NTNo`. Null out malformed `StandardNTN`
  values *before* grouping (don't just skip them logically) so garbage never persists.
- Winning row per NTN group = highest `|TotalDebit| + |TotalCredit|`; supplies
  `supplier_name`/`FBRTYPE`/`WhtTax%` for the merged Supplier.
- Keep **all** legacy `SupplierCode`s in a group, comma-joined onto
  `Supplier.custom_legacy_supplier_code` — not just the winner's.
- `WhtTax% = 0` → Tax Withholding Category named `Exempt` (both Filers and Non-Filers can
  have zero-rate rows).
- Opening balance: one Journal Entry **per legacy row** with nonzero `ClosingBalance`
  (rounded to 2dp before the zero-check), not one per merged Supplier — idempotent via
  `cheque_no = LEGACY-OB-<SupplierCode>`.

## Execution mechanics

- Dependency-free XLSX parsing convention: raw `zipfile`/`ElementTree`, no `openpyxl`
  (not a declared `aimatic` dependency).
- On a production site, take a backup first: `bench --site <site> backup`.
- Dry-run the parsing/grouping logic first — print summary counts only, no
  `insert`/`submit` calls — and sanity-check against a quick manual read of the source
  file before running for real.
- `bench console` piping gotcha: piping a raw multi-function script via
  `bench --site <site> console < script.py` causes IPython cell-splitting errors
  (`SyntaxError: return outside function`, spurious `NameError`s). Use instead:
  `echo 'exec(open("script.py").read(), globals())' | bench --site <site> console`
  — the explicit `globals()` argument is required, or functions defined via `exec()`
  can't see module-level constants.
- stdout is block-buffered when redirected to a log file — print statements don't flush
  until process exit, so tailing the log is not a reliable "still running" signal. Check
  process aliveness with `ps aux` instead.

## After running

- Verify against the source file to the penny: stock value (`SUM(Onhand*CurCost)`) vs.
  posted Stock Entry totals, `SUM(ClosingBalance)` vs. net posted Journal Entry amounts.
- Read every `FAILURE`/`FAILED` line the script prints — both reference scripts collect
  failures rather than aborting the whole run, so a clean-looking exit can still hide
  rejected rows.
- If a run partially fails, verify zero cross-references (SLE, Item Price, GL Entry,
  Stock Entry Detail) before deleting any partially-created doc, and prefer cancelling
  over deleting for anything with ledger entries.
- If this run surfaces a new mapping decision, update `import.md`/`supplierimport.md`
  **and** the "Legacy iPOS data migration" section of the top-level `CLAUDE.md` in the
  same session — don't let the decision live only in the script.
