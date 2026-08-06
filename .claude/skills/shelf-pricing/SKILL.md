---
name: shelf-pricing
description: Use for Purchase Receipt shelf-price propagation into branch Selling Price Lists, Item custom_mrp, branch Foodpanda Price Lists, POS Profile Foodpanda routing, price-update status/retry behavior, and cancel-safe Item Price Update Log restoration.
---

# Shelf pricing

Scoped to Purchase Receipt. Matching PO/PI fields are schema continuity only —
they do not authorize propagation.

## Gotchas

- Server `before_submit` rejects shelf price below cost after taxes; blank is OK.
- Application is explicit via governed branch + Foodpanda RPCs with independent
  confirm/status/retry. Dismissed dialog or non-Desk submit must leave a
  recoverable status, not a silent apply/loss.
- Writes require Buying Price Control or System Manager.
- Shelf/MRP → receipt branch Selling Price List + guarded `Item.custom_mrp`.
  Foodpanda → that branch's own Foodpanda Price List via
  `POS Profile.custom_is_foodpanda_profile`. No shared global Foodpanda list.
- Blank `custom_fp_price` leaves an existing Foodpanda price unchanged.
- `current_sale_price_preview.js` prefills blank `custom_shelf_price` only —
  never overwrites a manual value.
- Cancel restores only when current value still equals what that receipt wrote;
  respect `custom_mrp_source_date` so backdated receipts cannot clobber newer MRP.
- Branch Price Sheet Foodpanda grid/Excel import (`price_export.api`) is a second
  governed write surface: same role gate, writes `price_list_rate`+`custom_mrp`,
  audits via aggregate `Foodpanda Price Import Log` (not PR-scoped update logs).
  Stock/active/qty stay server-derived read-only.
- Branch owns Foodpanda vendor-automation SFTP CSV upload
  (`price_export.foodpanda_sftp`): per-branch host/port/username/Password on
  Branch, same CSV shape as Branch Price Sheet Download. Manual triggers on
  Branch and the report, plus a 15-minute cron that uploads each branch once
  its `custom_fp_sftp_schedule_time` is due (site timezone) when
  `custom_fp_sftp_enabled` is on. Partner API catalog sync on
  `Foodpanda Outlet` stays separate — never put SFTP secrets in fixtures,
  logs, or RPC responses.
