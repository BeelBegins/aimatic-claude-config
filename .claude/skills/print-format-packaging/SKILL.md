---
name: print-format-packaging
description: Use for adding, editing, selecting, renaming, packaging, or rendering an aimatic Print Format or Report, including POS receipts, purchase layouts, barcode or shelf labels, centralized Jinja HTML, and module-doc sync.
---

# Print formats and reports

Use Frappe's native module-document folders under the owning aimatic module.
Keep Print Format and Report JSON in the scrubbed-name directory; do not create a
custom sync system or modify an upstream module.

## Select and edit

1. Confirm the active format once against the target site when selection is
   runtime-dependent. For Electron POS receipts, query enabled custom POS Invoice
   formats; do not trust `POS Profile.print_format`.
2. Confirm the name does not collide with a Frappe/ERPNext format.
3. Edit layout HTML/CSS/Jinja in `aimatic/print_layouts/`. Keep the module JSON's
   `html` as the existing loader stub and put computed domain context in the
   appropriate `*_printing.py` helper.
4. Bump the JSON record's `modified` timestamp whenever shipped content changes;
   native sync skips an older or equal file.
5. Keep business-editable formats non-standard unless locking them is an
   explicit requirement.

For a rename, add the new module document and an idempotent post-model-sync patch
that removes the surviving old record after sync. Do not rely on a guarded
`rename_doc` after the new record already exists.

## Cache and verification

Clear the site cache after changing the layout loader, Jinja registrations,
printing context, or layout when cached output could remain. Site migrate or
cache mutation requires the `bench-ops` gate; local file edits do not.

Render one representative submitted document with the exact active format and
inspect the resulting HTML/PDF or printer-sized image. Check the changed values,
conditional blocks, escaping, widths, page breaks, and absence of stale inline
JSON/CSS. Add a return or duplicate rendering only when the change touches that
condition. Do not validate every format unless shared loader/context code changed.
