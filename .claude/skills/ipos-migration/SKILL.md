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
- `Pcs` UOM needs `Must be Whole Number = No` if source `Onhand` has decimals — set this
  *before* running stock entries, or `UOMMustBeIntegerError` aborts mid-batch.
- MRP fallback chain: source `MRP` if nonzero → else `rp × 1.18` if `rp` nonzero → else
  leave source value as-is.
- Item Group tree: majority-vote parent resolution for subcategories with conflicting
  parents; watch for spreadsheet footer/totals rows (blank `ItemCode`+`Description` but
  a formula string like `=SUBTOTAL(...)` in one cell) — skip these explicitly or they
  create a phantom Item on every re-run.
- Zero-valuation stock entry rows need `allow_zero_valuation_rate` set conditionally
  (`rate <= 0` only), never blanket.

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
