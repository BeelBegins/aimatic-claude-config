---
name: print-format-packaging
description: Adding, editing, or renaming a Print Format or Report in aimatic (POS receipts, purchase layouts, barcode/shelf labels, any new Script Report) — how the module-doc sync mechanism ships them, the rename gotcha, the centralized print_layouts/ convention, and the cache-clear step editors forget. Use whenever a print format's HTML/Jinja changes, a new print format or report is added, or one needs to be renamed.
---

# Print Format / Report packaging

## The mechanism: Frappe's native module-doc sync, not a custom one

All 9 of aimatic's Print Formats — `AIM Barcode Label`, `AIM Shelf Label A4`,
`Purchase Invoice Custom Layout`, `Purchase Receipt Custom Layout`, `POS 80x3276 v2`,
`POS Updated Print Layout`, `pos80x3276`, `Purchase Order Updated Lyaout`,
`Stock Acknowledgement` — ship as plain JSON
files, the same mechanism Frappe/ERPNext use for their own bundled print formats:

- `aimatic/label_printing/print_format/<scrubbed_name>/<scrubbed_name>.json` (2 files, module
  `Label Printing`) — `aim_barcode_label`, `aim_shelf_label_a4`.
- `aimatic/aimatic/print_format/<scrubbed_name>/<scrubbed_name>.json` (7 files, module `Aimatic`)
  — `pos80x3276`, `pos_80x3276_v2`, `pos_updated_print_layout`,
  `purchase_invoice_custom_layout`, `purchase_order_updated_lyaout`,
  `purchase_receipt_custom_layout`, `stock_acknowledgement`.

`Stock Acknowledgement` (Purchase Receipt, added 2026-07-17) is a warehouse-floor handover
document, deliberately stripped of everything `Purchase Receipt Custom Layout` shows (no vendor
rate/GST/margin/cost data) — just S#/barcode/description/UOM/ordered/received/rejected qty plus
three signature blocks (Received By / Checked By (Store Incharge) / Approved By). It reuses
`aimatic.purchase_printing.get_purchase_print_item_context` purely for the barcode lookup, ignoring
that helper's price fields.

A Print Format's own `module` field determines which app's folder Frappe looks in — that's why
the 6 non-label ones live under `aimatic/aimatic/print_format/` (module reassigned to `Aimatic`)
rather than ERPNext's `Accounts`/`Buying` folders, which aimatic obviously can't write into.

**A future custom Report follows the identical convention** — no custom sync module needed:
`<module-folder>/report/<scrubbed_name>/<scrubbed_name>.json` (`("core", "report")` is also in
Frappe's `IMPORTABLE_DOCTYPES`, same as `("printing", "print_format")`). The same is true of
`Workspace`/`Workspace Sidebar` (`("desk", "workspace")` / `("desk", "workspace_sidebar")`) if a
future change touches Desk navigation — see this bench's `CLAUDE.md` "Desk navigation" section
for that specific case's own route-collision gotcha.

## Why this replaced an earlier custom sync approach

A prior `printingformats/formats.json` + `setup.py` + one-time-patch mechanism (deleted) had two
real problems the native mechanism solves for free:
1. It only synced once (fresh install or a specific patch) — native sync
   (`frappe/modules/import_file.py:import_file_by_path`) re-runs on **every**
   `bench migrate`/fresh install, no patch needed for a future content edit.
2. It force-overwrote unconditionally — native sync only re-imports when the file's own
   `modified` timestamp is newer than the database's, so a live Desk edit is never silently
   clobbered by an unrelated migrate. `disabled` is additionally always preserved regardless of
   the file (`ignore_values["Print Format"] = ["disabled"]`) — a Desk-side enable/disable
   survives a migrate.

## To ship a new format or push a content change

Edit or add the file directly, **bump its `modified` timestamp** (the sync step compares this
against the DB — an unbumped timestamp means the change is silently skipped), then
`bench --site <site> migrate`.

## `standard: "No"` is deliberate — keep it that way

All 8 formats are `standard: "No"` so business staff can freely edit/enable/disable them from the
Desk UI (`standard: "Yes"` blocks *any* Desk save, including just toggling Disabled, outside
Developer Mode). Keep a new format's file at `standard: "No"` unless there's a specific reason to
lock it down.

## Before adding a new one: confirm it isn't already a core format

`grep -rl "<name>" apps/frappe apps/erpnext` before creating a new Print Format record — a prior
version of this packaging accidentally claimed ERPNext's own `POS Invoice Standard` and
force-disabled it. Never let a new format's name/module collide with a Frappe/ERPNext-shipped
one.

## Renaming an already-migrated Print Format needs a delete-old patch, NOT `frappe.rename_doc`

`[post_model_sync]` patches run **after** the module-doc sync step — so by the time such a patch
runs, the new-named record has already been freshly created from its own file. A guard like
`if exists(old) and not exists(new)` is therefore always false at that point, and the rename
silently never happens, leaving the old-named record orphaned in the database.

The correct pattern — copy `aimatic.patches.rename_purchase_stock_debit_note_layouts`: the patch
must **unconditionally delete any surviving old-named record**, not attempt a guarded rename.
(Real precedent: the two purchase layouts were originally named
`AIM Stock Debit Note - Purchase Invoice/Receipt`, renamed 2026-07-15 this way.)

## Centralized layouts, not inline JSON strings

All 8 formats' actual HTML/CSS/Jinja live as plain files in `aimatic/print_layouts/*.html`, not
inline in each format's own `<name>.json` (which would make every content change one giant
escaped-string diff with no syntax highlighting). Each format's own `html` field is reduced to a
1–2 line stub calling `aimatic.print_layout_loader.render_print_layout(name, doc, **context)`
(registered once in `hooks.py`'s `jinja.methods` — this one registration covers every layout
moved this way, past or future; `frappe`/`doc` are already available as globals inside the
rendered layout, so a layout needing only simple inline lookups can move over unchanged with no
`ctx` at all).

Domain-specific computed context lives in its own small helper, reused across every layout in
that domain — `aimatic.pos_printing.get_pos_receipt_context` for the 3 POS-receipt-shaped
layouts (`POS 80x3276 v2`, `pos80x3276`; `POS Updated Print Layout` doesn't need it yet),
`aimatic.purchase_printing.get_purchase_print_item_context` for the 2 purchase custom layouts. A
new domain (e.g. a future Sales Order layout with its own lookups) gets its own new
`*_printing.py` file — don't bolt it onto an existing unrelated one. This is aimatic's own
convention layered on top via `frappe.render_template()`, not a Frappe built-in (Print Format has
no native sidecar-file split the way `Server Script.get_code_fields()` does).

## Editing any of these files needs a cache clear to take effect

A new `hooks.py` `jinja.methods` entry, or an edit to `print_layout_loader.py` /
`pos_printing.py` / `purchase_printing.py` itself, is picked up on the *next fresh process*, but
Frappe's compiled-Jinja-environment cache (Redis-backed) can still serve a stale version
otherwise. Run `bench --site <site> clear-cache` after such an edit — a file save alone is not
enough to verify the change actually renders.

## `bench console` scripts that reload/mutate must commit explicitly

A piped/non-interactive `bench console` session does not auto-commit on exit. A change (e.g.
`frappe.reload_doc(..., force=True)` to force-reload a format) is visible within that same
process but silently rolls back once the process exits without an explicit
`frappe.db.commit()`. This bit the project directly: a "reload the print format" step appeared to
work (verified by rendering in the same process) but never actually persisted — the next site's
console session saw the old content again. `bench migrate`/patches are unaffected (they commit on
their own); this only matters for ad-hoc scripts.

## Working safely

Update the "Print Format packaging" section of this bench's `CLAUDE.md` in the same session if
the format count/list changes, a new domain-specific `*_printing.py` helper is added, or the
sync/rename mechanics change.
