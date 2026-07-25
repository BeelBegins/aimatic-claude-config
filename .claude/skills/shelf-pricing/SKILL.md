---
name: shelf-pricing
description: Purchase Receipt shelf-price propagation into branch Selling Price Lists, Item.custom_mrp, and each branch's own Foodpanda Price List — validate_shelf_price_before_submit, apply_branch_price_update/apply_foodpanda_price_update, the lazy branch-price-list creation, custom_is_foodpanda_profile, or Item Price Update Log audit/restore-on-cancel. Use whenever shelf pricing, MRP propagation, or the Foodpanda price list comes up.
---

# Shelf pricing (Purchase Receipt only)

Purchase Invoice carries the same `custom_shelf_price`/`custom_mrp` fields but is **deliberately
unwired** — don't extend this feature onto Purchase Invoice without checking whether that's now
actually wanted; as of writing it's Purchase-Receipt-only by design, not an oversight.

## Validation vs. application are two separate mechanisms — don't conflate them

- **Validation is a hook**: `shelf_pricing/events.py:validate_shelf_price_before_submit`
  (`before_submit`) hard-throws `Row #{idx}: Shelf Price (...) cannot be less than Cost After
  Taxes (...)` for any row where `custom_shelf_price` is set below `custom_price_after_taxes`.
  Rows with no shelf price entered skip validation entirely — the field isn't mandatory (plenty
  of PR rows are non-retail restock with no shelf price at all).
- **Applying the update is client-script-driven, not a hook.** The fixture-tracked Client Script
  `"Shelf Pricing Popups (Claude)"` shows two sequential Yes/No dialogs on submit (branch
  pricing, then **always** Foodpanda regardless of the first answer), calling the whitelisted
  `shelf_pricing.api.apply_branch_price_update` / `apply_foodpanda_price_update` (verified live:
  `shelf_pricing/api.py:35` / `:92`) — or their `skip_*` counterparts on "No". Both `apply_*` are
  gated on the `Buying Price Control` role (or `System Manager`); declining or lacking the role
  both leave `Purchase Receipt.custom_branch_price_update_status` /
  `custom_foodpanda_price_update_status` at `Pending`/`Skipped` rather than silently failing —
  the form also gets "Update Branch Price"/"Update Foodpanda Price" **retry buttons** whenever
  the corresponding status isn't `Updated`. Any change here must preserve that retry safety net
  (a dismissed dialog, a denied permission, or a receipt submitted outside the Desk UI must still
  be recoverable).

## Every branch gets two Price Lists, initialized together at Branch creation

`branch_management.events.initialize_branch_selling_price_list` (Branch `after_insert`, name kept
for hook-registration stability even though it now does two things) calls **both**
`shelf_pricing/utils.py:get_or_create_branch_price_list` and
`get_or_create_branch_foodpanda_price_list`, so every branch gets its own normal selling list
(`<Branch> Selling Price List`) and its own Foodpanda-only list (`<Branch> Foodpanda Price List`)
immediately, not deferred until first use. Both are enabled, **selling-only** Price Lists
(`selling=1`, `buying=0`), linked onto `Branch.default_selling_price_list` /
`Branch.default_foodpanda_price_list` respectively. The normal list's creation copies every
selling `Item Price` from `Selling Settings.selling_price_list` in once as a baseline; the
Foodpanda list does **not** — it starts empty and is populated item-by-item by
`apply_foodpanda_price_update` from Purchase Receipts, same as the pre-2026-07-26 global list
was. Both helpers remain idempotent fallbacks for legacy branches and are safe to call again.
Existing or convention-named lists must be enabled, selling, and not buying; an invalid list is
rejected rather than silently accepted. The Finance Setup console's **Initialize branch price
lists** action (`retail_finance_setup.api.initialize_branch_selling_price_lists`, Accounts
Manager/System Manager only) still only backfills the **normal** list for older branches — it was
not extended to the Foodpanda list; `patches.create_branch_foodpanda_price_list` is what backfills
the Foodpanda list for branches that existed before 2026-07-26.

## Foodpanda pricing became per-branch on 2026-07-26 — `custom_is_foodpanda_profile` is the routing flag

**Before 2026-07-26**: one single global `"Foodpanda"` Price List shared by every branch
(`get_or_create_foodpanda_price_list`, now removed), with no field distinguishing a "Food Panda"
POS Profile from a normal one — pure name-matching convention. This silently broke: since
`branch_management.events.apply_pos_profile_branch_price_list` treats every branch-linked POS
Profile identically, it unconditionally forced a Food Panda POS Profile's `selling_price_list`
back onto its **branch's normal list** on every single save, discarding any manual assignment to
the Foodpanda list with no error — the incident that prompted this whole rework.

**Now**: `POS Profile.custom_is_foodpanda_profile` (Check, added by
`patches.create_branch_foodpanda_price_list`) is the explicit, permanent marker.
`apply_pos_profile_branch_price_list` checks it (via `getattr(doc, "custom_is_foodpanda_profile",
0)`, not `.get()` — keeps it compatible with plain objects in unit tests) and routes to
`get_or_create_branch_foodpanda_price_list(doc.branch)` instead of the normal-list function when
set. `get_or_create_branch_price_list`'s own POS-Profile-repoint loop (on first creation of a
branch's normal list) now excludes `custom_is_foodpanda_profile=1` profiles, and
`get_or_create_branch_foodpanda_price_list` has the mirror-image loop that only repoints
Foodpanda-flagged profiles. There is still no UI/validation stopping a non-Foodpanda POS Profile
from having this box checked by mistake — it's a plain field, trust the person configuring it.

`apply_foodpanda_price_update` (`shelf_pricing/api.py`) now requires the Purchase Receipt to have
a `branch` set (same guard `apply_branch_price_update` already had) and writes into
`get_or_create_branch_foodpanda_price_list(doc.branch)` instead of the old global list; the
`branch` parameter to `upsert_item_price`/`log_price_update` is now `doc.branch` instead of always
`None`, so `Item Price Update Log` rows for Foodpanda updates are now branch-attributed too.
`restore_prices_on_cancel` needed no change — it restores by whatever `price_list` value was
logged, so it's already price-list-agnostic.

**Migration for branches that existed before 2026-07-26**:
`patches.create_branch_foodpanda_price_list` (a) creates the two new fields above, (b)
bootstrap-flags any existing POS Profile whose name contains "foodpanda"/"food panda"
(case/space-insensitive) since that's the only signal available for a profile created before the
checkbox existed, (c) if the site has **exactly one** Branch still missing
`default_foodpanda_price_list` and an existing `"Foodpanda"` Price List, repoints that legacy
global list onto that one branch (preserves its live item prices) rather than creating a
duplicate — mirrors `tax_formula_setup`'s "only repair when unambiguous" precedent; multi-branch
sites instead get a fresh list created per branch, and (d) immediately repoints each newly-flagged
profile's `selling_price_list` rather than waiting for its next manual save. `FOODPANDA_PRICE_LIST
= "Foodpanda"` is kept as a constant in `utils.py` purely so this patch can find that legacy name;
nothing else creates or references it anymore.

## Foodpanda price source moved from `custom_mrp` to its own field, `custom_fp_price` (2026-07-26)

`Purchase Order Item` / `Purchase Receipt Item` / `Purchase Invoice Item` all carry an identical
`custom_fp_price` (Currency) field now — added to all three for schema consistency with the rest
of the purchase pipeline (matching how `custom_mrp`/`custom_shelf_price` already exist across all
three), even though only Purchase Receipt's `apply_foodpanda_price_update` actually reads it.
`custom_mrp` keeps doing everything it already did elsewhere (global `Item.custom_mrp`, the
branch's normal selling list) — this only decouples the Foodpanda channel specifically, since
tying Foodpanda pricing to the same field as everything else made it impossible to set a
different Foodpanda price without also changing MRP everywhere else.

**Prefill is a live client-side convenience only**, same class of mechanism as
`purchase_history_autofill` but a different source: `public/js/foodpanda_price_prefill.js`
(shared across all three doctypes, registered in `hooks.py`'s `doctype_js`) calls
`shelf_pricing.api.get_current_foodpanda_price(item_code, branch)` on `item_code`/`branch` change
and fills `custom_fp_price` with the branch's **current** Foodpanda Price List rate for that item,
only if the field is still blank (never overwrites a manual entry). This is *not* guaranteed
server-side — a row added another way (e.g. "Get Items From Purchase Order") keeps whatever value
it already had, and `apply_foodpanda_price_update` falls back to its existing "leave current FP
price untouched" behavior for that row if `custom_fp_price` is blank. `get_current_foodpanda_price`
deliberately never calls `get_or_create_branch_foodpanda_price_list` — a plain read must not have
the side effect of creating that Price List.

Because this prefill mechanism has a fundamentally different source (current price-list state, not
"last submitted document's value"), `custom_fp_price` is explicitly excluded from
`purchase_history_autofill`'s own schema-driven field discovery (`_CURRENT_PRICE_LIST_DENY` in
`purchase_history_autofill/utils.py`) — otherwise both mechanisms would compete to prefill the
same field with different values.

Rate and MRP on the resulting `Item Price` row are both still set flat, `= custom_fp_price`, no
markup-percentage config — same explicit product decision as before, only the source field
changed. On the very first Foodpanda `Item Price` row for an item with no `custom_fp_price`
entered, it falls back to that item's `Standard Selling` rate (initial-setup convenience). Every
later receipt with a blank FP Price leaves an existing Foodpanda price **untouched** rather than
zeroing it — never treat "no FP Price on this receipt" as "clear the Foodpanda price."

## Audit trail and cancel-safe restore

`Item Price Update Log` — one row per item/price-list/field actually changed
(`purchase_receipt`/`branch`/`old_value`/`new_value`/`updated_by`/`update_datetime`; a **blank**
`price_list` means the row is the global `Item.custom_mrp` write, not a price-list rate).
`events.py:restore_prices_on_cancel` (verified live: `events.py:25`, `on_cancel`) walks this log
for the cancelled receipt and restores `old_value` **only if the target's current value still
equals what this receipt last set** — otherwise a later receipt or manual edit already superseded
it and is left alone. Never restore unconditionally; that would clobber a legitimate later change.

`Item.custom_mrp` is gated the same way `item_pricing` gates cost price: a
`custom_mrp_source_date` field means a backdated receipt can't clobber a more recent MRP. Any new
write path to `custom_mrp` must respect this date check, not write directly.

## Retired mechanism — do not re-enable

The old `"Update Price function call"` Client Script + `"Update selling price rate"` Server
Script (`api_method: update_selling_price`) is **disabled, not deleted**, in the fixture JSON
(2026-07-14). It only ever pushed `custom_shelf_price` into the single global `Selling Settings.
selling_price_list`, had no branch/Foodpanda awareness, and — worth remembering if anything like
it resurfaces — had `allow_guest: 1` on the Server Script (callable unauthenticated). `shelf_
pricing` fully replaces it; do not re-enable it or reintroduce an unauthenticated price-write
endpoint.

## Working safely

Update the `shelf_pricing/` section of this bench's `CLAUDE.md` in the same session if the
propagation targets, the lazy-creation trigger, or the Foodpanda pricing rule changes.
