---
name: shelf-pricing
description: Purchase Receipt shelf-price propagation into branch Selling Price Lists, Item.custom_mrp, and the global Foodpanda Price List — validate_shelf_price_before_submit, apply_branch_price_update/apply_foodpanda_price_update, the lazy branch-price-list creation, or Item Price Update Log audit/restore-on-cancel. Use whenever shelf pricing, MRP propagation, or the Foodpanda price list comes up.
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

## Branch price list is initialized once per branch

`shelf_pricing/utils.py:get_or_create_branch_price_list` creates `<Branch> Selling Price List` as an
enabled, **selling-only** Price List (`selling=1`, `buying=0`), copies every selling `Item Price`
from `Selling Settings.selling_price_list` into it once as a baseline, links it onto
`Branch.default_selling_price_list`, and repoints existing POS Profiles for that branch. Creation
is now triggered immediately by `branch_management.events.initialize_branch_selling_price_list`
on Branch `after_insert`, not deferred until the first Purchase Receipt. The helper remains the
idempotent fallback for legacy branches and receipt updates. The Finance Setup console's
**Initialize branch price lists** action calls
`retail_finance_setup.api.initialize_branch_selling_price_lists` for older branches; only Accounts
Manager/System Manager may run it. `apply_pos_profile_branch_price_list` runs on POS Profile
validation, so profiles created after Branch initialization also use the correct branch list.
Existing or convention-named lists must be enabled, selling, and not buying; an invalid list is
rejected rather than silently accepted.

## Foodpanda price is flat `= custom_mrp` — no markup-percentage config, by explicit decision

Rate and MRP both set to `custom_mrp`. Don't build markup-percentage configurability
speculatively — it was explicitly rejected as out of scope for now. On the very first Foodpanda
`Item Price` row for an item with no `custom_mrp` entered, it falls back to that item's
`Standard Selling` rate (initial-setup convenience). Every later receipt with a blank MRP leaves
an existing Foodpanda price **untouched** rather than zeroing it — never treat "no MRP on this
receipt" as "clear the Foodpanda price."

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
