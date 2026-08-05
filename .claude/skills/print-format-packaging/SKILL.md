---
name: print-format-packaging
description: Use for adding, editing, selecting, renaming, packaging, or rendering an aimatic Print Format or Report, including POS receipts, purchase layouts, barcode or shelf labels, centralized Jinja HTML, and module-doc sync.
---

# Print formats and reports

Use Frappe native module-doc folders under the owning aimatic module. No custom
sync system; do not edit upstream modules.

## Gotchas

- Electron POS receipts: query enabled custom POS Invoice formats — do not trust
  `POS Profile.print_format`.
- Edit HTML/CSS/Jinja in `aimatic/print_layouts/`. Module JSON `html` stays the
  loader stub; domain context belongs in `*_printing.py`.
- Bump JSON `modified` on shipped edits — native sync skips older/equal files.
- Keep formats `standard: "No"` so staff can edit unless locking is required.
- Rename = new module doc + idempotent post-model-sync patch that deletes the
  surviving old record. Do not `rename_doc` after the new record already exists.
- Clear site cache after loader/Jinja/layout changes. Site mutate → `bench-ops`.
