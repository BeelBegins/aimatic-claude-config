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

## Which POS receipt format actually prints — `POS Profile.print_format` is NOT it

The Electron client (`Posapplication/src/core/sale-refund.ts`'s `getPosReceipt`/
`findPosInvoicePrintFormat`) never reads `POS Profile.print_format`. It queries `Print Format`
directly for `doc_type = "POS Invoice" AND disabled = 0`, preferring a `standard: "No"` (custom)
row over a core one, then hits Frappe's real `/printview` route with that name. So the format a
cashier's receipt actually renders with is whatever that query resolves to **on that site right
now** — not whatever a POS Profile's own field happens to say (that field may be stale/unused).
Confirmed 2026-07-20 across all three sites: `POS 80x3276 v2` is the only enabled, custom
`POS Invoice` format everywhere, so it's the one actually in use on `szl`/`siezal`/`hsm` alike,
even though `szl`'s and `hsm`'s POS Profiles still say `print_format: "pos80x3276"` in their own
field (harmless — that field is simply dead for this flow) and `pos80x3276` itself is `disabled:
1` on both those sites (and has been since creation — check `frappe.db.get_value("Print Format",
"pos80x3276", "disabled")` before assuming it's live anywhere). **Before touching any POS receipt
layout, run the same query** (`frappe.get_all("Print Format", filters={"doc_type": "POS Invoice",
"disabled": 0}, fields=["name", "standard"])`) **against the actual site in question** rather than
trusting the POS Profile field — editing the wrong format is invisible until someone prints.

## POS receipt fix, 2026-07-20: 80mm→78mm width + bottom Tendered/Change block

A cashier reported receipts cutting off a little on the right edge on physical 80mm thermal
printers, and asked for a Tendered Amount/Change section. Root cause of the cut-off: the layout's
`@page`/`html`/`body`/`.print-format`/`.page-break`/`.pos-receipt` widths were all hard-pinned to
`80mm !important` — the nominal roll width, not the printer's actual printable area, which is
narrower once the printer's own physical margins are accounted for. Fixed in **both**
`pos_80x3276_v2.html` and `pos80x3276.html` (kept in sync even though only the v2 one is live per
the section above — no reason to let the disabled one drift further) by changing every one of
those width declarations from `80mm` to `78mm` (`.pos-receipt`'s horizontal padding also trimmed
10px→8px each side to keep roughly the same usable content width at the new total). Verified via
`frappe.get_print(doctype="POS Invoice", name=..., print_format=...)` + `wkhtmltoimage` rendering
against real submitted invoices on all three sites — zero `80mm` occurrences left, receipt renders
fully inside a 295px-wide (78mm @ 96dpi) frame with no overflow.

For the payment section: both layouts already had a mid-receipt "Paid"/conditional-"Change" row
(right after the totals block) — per explicit product decision this was left untouched, and a
**new, separate** "Tendered / Change" box was added right before the final `<div class="rc-footer">`
(after the FBR strip, so it's the true last content block before Terms/Thank-you), always showing
both `Tendered Amount` (`doc.paid_amount`) and `Change` (`doc.change_amount or 0`) — unconditional,
unlike the existing mid-receipt Change row which stays hidden when zero.

Also cleaned up while in there: `pos80x3276.json`'s Print Format record carried a **separate legacy
`css` field** (pre-dating the `print_layouts/*.html` centralization, still hard-coded to the old
80mm values) that `pos_80x3276_v2.json` never had — Frappe's `get_print_style()`
(`frappe/www/printview.py`) appends this field's content as an independent `<style>` block
regardless of `print_format_type`, so a stale `css` field is a real (if here empirically harmless,
since it renders before the layout's own `<style>` in DOM order) source of drift from the
centralized layout file. Removed the field entirely so `pos80x3276` styling comes solely from its
`print_layouts/pos80x3276.html`, same as every other centralized format.

Remember the `modified`-timestamp-bump step (see above) for both `<name>.json` files, then
`bench --site <site> migrate` **and** `clear-cache` on every site — this was applied to
`szl`/`siezal`/`hsm` together to keep the fixture-tracked files and all three live sites in sync,
since a print layout bug like this is a code-level defect, not per-site data.

## Item-row barcode text, and Gift Voucher suppression on a reprint (2026-07-21)

Two related `get_pos_receipt_context` (`aimatic/pos_printing.py`) changes, both affecting
`pos_80x3276_v2.html`/`pos80x3276.html`'s per-item `.rc-item-code` line:

- **Barcode text, not the item code, is now what prints on that line.** `get_pos_receipt_context`
  returns an `item_barcodes` dict keyed by `POS Invoice Item.name`, resolved same as
  `purchase_printing.get_purchase_print_item_context`'s barcode chain: the row's own scanned
  `barcode` field first, then the item master's first `Item Barcode` row
  (`_get_primary_barcodes`, a POS-receipt-local copy of `purchase_printing`'s helper of the same
  name), falling back to the item code itself only when the item has no barcode registered at
  all. Both templates read it as `{{ ctx.item_barcodes[item.name] }}` instead of
  `{{ item.item_code }}` — plain text, deliberately **not** a rendered barcode image (explicit
  product decision — a scannable graphic was considered and rejected in favor of a smaller
  text-only change).
- **A duplicate/reprint must never show Gift Voucher issuance/redemption again.** The Electron
  client's "Duplicate Receipt" action (`getDuplicateReceipt` in `Posapplication`'s
  `src/core/sale-refund.ts`) used to just re-fetch the exact same `/printview` HTML as the
  original print and overlay a "DUPLICATE COPY" banner — but `get_pos_receipt_context` recomputes
  `gift_voucher_issued`/`gift_voucher_redeemed` live from the `Gift Voucher` doctype on *every*
  render, with nothing distinguishing an original print from a reprint, so a reprint kept showing
  "You've Earned a Gift Voucher!" (QR code included) as if it had just happened. Fixed by having
  the client tag the duplicate request with `?is_duplicate=1` (a real, if unregistered, query
  param — confirmed via `frappe/www/printview.py` that any extra query param lands in
  `frappe.form_dict` harmlessly) and having `get_pos_receipt_context` read
  `frappe.form_dict.get("is_duplicate")` to return `None` for both Gift Voucher keys when set —
  the templates already guard both blocks with `{%- if gv_issued -%}`/`{%- if gv_redeemed -%}`,
  so `None` suppresses them with no template change needed. Loyalty Points display is deliberately
  untouched on a reprint (only Gift Voucher was in scope). Client-side, `getPosReceipt`/
  `getDuplicateReceipt` share one new `fetchPosReceiptHtml(posInvoice, isDuplicate)` — the
  duplicate-flavored render is never written to nor read from `deps.db.cacheReceiptHtml`'s cache
  key for that invoice, so it can never contaminate (or be silently served in place of) the
  original print's cached copy.
- **Verification gotcha hit while testing this**: checking for the Gift Voucher block's presence
  by searching rendered HTML for the substring `rc-gift-voucher` gives a false positive — that
  class name is always present in the `<style>` block's CSS rule (`.rc-gift-voucher { ... }`)
  regardless of whether the `<div class="rc-gift-voucher">` itself actually rendered. Search for
  the literal opening tag (`<div class="rc-gift-voucher">`) instead. Also, calling
  `frappe.get_print(...)` twice in the same `bench console` process to compare "normal" vs.
  "duplicate" output is unreliable on its own — `frappe.website.utils.cache_html` caches rendered
  page HTML keyed only on path (`"printview"`, ignoring query string) whenever
  `website_utils.can_cache()` is true, which it is inside a bare console call (no real
  `frappe.request`, so the `if frappe.request and frappe.request.query_string: return False`
  short-circuit that protects real HTTP `/printview` requests never triggers). Set
  `frappe.local.no_cache = True` before such a comparison, or just test
  `get_pos_receipt_context(doc)`'s return value directly instead of the full rendered HTML.

## Working safely

Update the "Print Format packaging" section of this bench's `CLAUDE.md` in the same session if
the format count/list changes, a new domain-specific `*_printing.py` helper is added, or the
sync/rename mechanics change.
