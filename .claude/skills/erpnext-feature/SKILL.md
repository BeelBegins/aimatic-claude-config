---
name: erpnext-feature
description: Adding or modifying a feature, doctype hook, doc_event, custom field, or Property Setter inside apps/aimatic — new business logic touching Sales Order/Sales Invoice/Purchase Order/Purchase Receipt/Stock Entry/Item/Customer/Supplier/Branch, or any change wired through hooks.py. Never modify apps/frappe, apps/erpnext, or apps/hrms directly.
---

# ERPNext feature development in aimatic

## Scope boundary

`apps/frappe`, `apps/erpnext`, `apps/hrms` are upstream dependencies (installed via
`bench get-app`) — never edit them. All custom behavior belongs in `apps/aimatic`. Before
writing new logic, check `apps/aimatic/aimatic/hooks.py` for existing `doc_events` wiring on
the doctype you're touching, so you don't duplicate or conflict with an existing hook.

## Hook-ordering gotcha (learned the hard way, don't repeat it)

For the `"validate"` doc_event specifically, Frappe's hook composer calls the doctype
controller's own `validate()` method **first**, then app-registered `doc_events["validate"]`
hooks **afterward** — and if the controller's own `validate()` raises, the hooks loop never
runs. If your hook needs to fix/set something *before* the doctype's own core validation can
object to it (e.g. correcting `cost_center`/`warehouse` before ERPNext's own subcontracting
validation checks them), register it on `"before_validate"` instead — a distinct, strictly
earlier lifecycle event. `branch_management/events.py:apply_branch_defaults` is the concrete
precedent for this.

## Fixtures

Custom Field, Property Setter, Client Script, and Server Script are fixture-tracked (see
`hooks.py`'s `fixtures`, excluding HRMS doctypes in `hrms_fixture_doctypes`). After changing
any of these from the Desk UI, run
`bench --site szl export-fixtures --app aimatic` in the same session so the change lands in
git — otherwise it only exists in that site's database.

## Branch / Warehouse / Cost Center model

This app enforces zero generic fallback warehouses or cost centers — every stock movement and
GL entry must land in a branch-specific warehouse/cost-center. Any new feature touching Sales
Order/Sales Invoice/Delivery Note/Purchase Order/Purchase Invoice/Purchase Receipt/Stock Entry
must respect `branch_management/events.py:apply_branch_defaults` rather than introducing its
own defaulting logic. Two things that bite people:
- A User Permission on `Branch` does **not** cascade to `Cost Center` or `Warehouse` Link
  fields — those need their own separate User Permission rows, or a branch-restricted user
  still sees every branch's cost centers/warehouses in dropdowns (though the actual saved
  value still gets force-corrected for non-override users).
- GL Entry's `cost_center` comes from each **row's own** `cost_center` field, not the parent
  document's — always set row-level cost_center/warehouse explicitly when scripting
  transactions, don't trust auto-default.
- POS Invoice (including `is_pos` Sales Invoices) is deliberately skipped by
  `apply_branch_defaults` — it's built server-side from POS Profile already.

## `fetch_from` gotcha

If a field's value looks like it's copying the wrong thing (e.g. a Link's own name instead of
one of its own fields), check
`frappe.get_meta(doctype).get_field(fieldname).fetch_from` for a wrong dotted path before
assuming it's a logic bug. Also remember `fetch_from` only populates on create/link-change,
never live — if a value needs to stay current after the source changes, a direct write on
`on_submit`/similar is required instead (see `item_pricing/events.py` for that pattern).

## Patches

New one-off data/schema patches go in `apps/aimatic/aimatic/patches/`, registered in
`patches.txt` under `[pre_model_sync]` (before doctype migration — role creation, things that
don't depend on new schema) or `[post_model_sync]` (after migration — custom fields, defaults
that depend on the migrated schema).

## Standard workflow

- `bench --site <site> migrate` after any doctype/patch change.
- `bench build --app aimatic` after any `public/` JS/CSS change.
- Update the relevant module section of the top-level `CLAUDE.md` in the same session if this
  change adds/removes a module, hook, doctype, or introduces a gotcha a future session would
  need to know — don't defer it.
