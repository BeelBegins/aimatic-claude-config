---
name: shelf-pricing
description: Use for Purchase Receipt shelf-price propagation into branch Selling Price Lists, Item custom_mrp, branch Foodpanda Price Lists, POS Profile Foodpanda routing, price-update status/retry behavior, and cancel-safe Item Price Update Log restoration.
---

# Shelf pricing

Keep this feature scoped to Purchase Receipt. Matching fields on Purchase Order
or Purchase Invoice provide schema continuity but do not authorize propagation
from those documents.

## Validation and application

- Retain server `before_submit` validation that a supplied shelf price is not
  below cost after taxes. A blank shelf price remains allowed.
- Keep application explicit through the governed branch and Foodpanda RPCs.
  Preserve independent confirmation, authorization, status, skip, and retry
  behavior for both targets. A dismissed dialog, permission denial, or non-Desk
  submit must leave a recoverable status rather than silently applying or losing
  the update.
- Restrict price writes to Buying Price Control or System Manager through the
  current endpoints. Never revive an unauthenticated or generic price writer.

## Routing

- Send normal shelf/MRP updates to the receipt's branch Selling Price List and
  the guarded global `Item.custom_mrp` field.
- Route Foodpanda updates to the receipt branch's own Foodpanda Price List, using
  `POS Profile.custom_is_foodpanda_profile` to select that list. Do not return to
  a shared global Foodpanda list or name-based routing.
- Read Foodpanda price from `custom_fp_price`. Blank means leave an existing
  Foodpanda price unchanged; only the established first-price fallback may seed
  a missing row.
- Keep branch Price List helpers idempotent and validate that resolved lists are
  enabled, selling-only, and assigned to the correct branch field.

## Audit and cancellation

Log every changed target to `Item Price Update Log` with old/new values, receipt,
branch, price list, actor, and time. On cancellation, restore only when the
current value still equals what that receipt last wrote; never overwrite a later
receipt or manual edit. Respect `custom_mrp_source_date` so a backdated receipt
cannot replace newer MRP.

## Verify narrowly

Test one receipt for normal branch price, Foodpanda price, blank-value behavior,
status/retry, unauthorized access, and cancellation after a later edit when
relevant. Confirm the exact price lists and audit rows; expand to purchase-cycle
tests only when purchase validation or lifecycle logic also changes.
