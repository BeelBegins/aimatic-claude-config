---
name: loyalty-gift-voucher
description: Working on item-group-weighted loyalty points or Gift Voucher bracket issuance/redemption in aimatic — Item Group loyalty rate cascade, Loyalty Point Entry correction, Gift Voucher Criteria brackets, voucher-as-payment-row redemption, or anything in preview_cart/submit_online_sale's gift_voucher_code param. Use whenever loyalty rate, voucher bracket, or gift voucher redemption logic changes.
---

# Loyalty + Gift Voucher (customer incentive features)

Two features driven off `POS Invoice` submit/cancel (`hooks.py`'s `doc_events["POS Invoice"]`,
`on_submit`/`on_cancel` keys shared with `fbr_pos`'s own handlers on the same doctype — check
`hooks.py` before assuming a new handler is the only one running on that event).

## Loyalty: only the earning rate is custom, everything else is stock ERPNext

Loyalty reuses ERPNext's own Loyalty Program / Loyalty Point Entry ledger, redemption, and expiry
as-is — this was a deliberate rejection of a fully independent ledger. The only custom part is
the *earning rate*: item-group-weighted instead of ERPNext's flat whole-invoice factor.

- `loyalty/item_group_rate.py` cascades an Item Group's configured rate down the tree to its
  children. `custom_loyalty_rate_configured` (checkbox) distinguishes "no override, inherit from
  ancestor" from "explicit override to 0" — don't collapse these into a single nullable-rate
  field, the distinction is load-bearing.
- `loyalty/events.py:on_submit_correct_loyalty_points` corrects ERPNext's auto-created Point
  Entry **in place, after submit** (ERPNext creates one first using its own flat rate; this
  function then recalculates using the per-item-group weighted rate) — including the returns
  case. Points/brackets are calculated off the customer-facing line amount (`row.amount`), not
  a tax-exclusive snapshot.
- The `Item Group Hierarchy` report (`aimatic/aimatic/report/item_group_hierarchy/`) audits this
  cascade — every Item Group's ancestor chain, whether it has an explicit override, and both its
  own and *effective* (nearest-configured-ancestor) rate. **Keep this report's logic in sync**
  with `item_group_rate.py:get_item_group_loyalty_rate` if the inheritance rule ever changes —
  it's a hand-maintained parallel implementation, not a shared call.

## Gift Voucher: value brackets, issued on submit, redeemed later by code

`gift_voucher/events.py:on_submit_issue_gift_voucher` auto-issues a voucher based on configured
value brackets (`Gift Voucher Criteria`, matched via `_find_matching_criteria(company, branch,
grand_total)` in `events.py` — bracket matching is on invoice `grand_total`, resolved per
company **and branch** via `fbr_pos.payload_builder.get_invoice_branch`).
`on_cancel_gift_voucher` cancels/reactivates on invoice cancel. Redemption is a separate later
sale: `gift_voucher/api.py`'s `list_customer_gift_vouchers` / `validate_gift_voucher_code`, and
`offline_pos/api.py`'s `preview_cart` / `submit_online_sale` both take a `gift_voucher_code`
param.

**Hard product decisions — these were explicit rejections of the "obvious" alternative, don't
silently reintroduce it:**
- Gift Voucher Criteria branch matching requires an **exact** branch match — no blank-branch,
  company-wide fallback row. Every branch needs its own criteria row.
- Redemption minimum is `Gift Voucher Criteria.minimum_redemption_value`, a dedicated field
  **independent of** that bracket's own `min_value` — not derived from it. (Confirmed live in
  `gift_voucher/api.py`.)
- Excess voucher value over a bill is forfeited on redemption — there is no
  partial-redemption/remaining-balance state to carry forward.
- Vouchers are auto-issued on submit and redeemed by code on a *later* sale — not silently
  auto-applied at issuance, and not a fully manual admin-only process either.

## Redemption is a Mode of Payment row, never a discount — this is FBR-driven, not cosmetic

Redemption is modeled as a server-only **"Gift Voucher" Mode of Payment row** (created by
`patches.create_gift_voucher_mode_of_payment`), **never added to any POS Profile's payment
list** so a cashier can't pick it manually — deliberately, and never as a Grand Total discount.
The reason is FBR compliance, not style: `fbr_pos` computes its e-invoicing payload from
per-item `row.amount`, so a Grand-Total discount would under-report the sale value to FBR
relative to what the customer actually paid. A payment row (the same technique ERPNext's own
loyalty-point redemption uses) has zero effect on `net_total`/`grand_total`, so the FBR payload
stays correct. **Do not "simplify" voucher redemption into a discount line** — that would
reintroduce under-reporting to a live government e-invoicing integration.

Redemption is finalized race-safely (conditional `UPDATE ... WHERE status='Active'`), only
**after** `doc.submit()` succeeds, inside the same savepoint that handles idempotent
`terminal_invoice_id` replay in `offline_pos/api.py` — don't move voucher finalization earlier
in the flow, or a failed/retried submit could burn a voucher with no corresponding sale.

## Client-side redemption (Electron) — applied via Benefits (F7), not Payment (F6)

Confirmed live in `Posapplication/src/renderer/renderer.ts`/`index.html`: a cashier enters or
scans a gift voucher code in the **Benefits (F7)** dialog (`benefits-gift-voucher-code`,
alongside loyalty points and coupon code — all three share this one dialog), which sets
`appliedBenefits.giftVoucherCode`. That value flows into `preview_cart`'s `gift_voucher_code`
param for the live cart preview, and into `submit_online_sale`'s `salePayload.gift_voucher_code`
at final submission — this is the same server contract documented above, just showing where the
client actually collects it. This is a **different dialog from Payment (F6)** — see the
`offline-pos` skill for that one; benefits are always applied before a cashier opens Payment, not
during it.

**Hard client-side constraint**: gift voucher redemption requires ERPNext online validation — an
applied voucher **blocks offline sale** entirely (`"Gift voucher redemption requires ERPNext
online validation. Remove voucher to sell offline."`). A cashier must remove the voucher to
complete an offline-queued sale. Any new redemption-adjacent client feature must preserve this —
don't let a voucher amount get silently estimated/trusted offline.

## Real incident, 2026-07-16: "Gift Voucher" as a selectable payment mode was a live fraud hole

Confirmed on production `siezal`: all 4 real checkout counters (`S1GT Counter 1-4`) had
**"Gift Voucher" configured directly in their POS Profile payment methods list**, selectable in
the Electron client's F6 Payment screen like Cash/Credit Card. `offline_pos/api.py`'s
`_validate_and_set_payments` trusted `allowed_modes` from the POS Profile's own config, and its
docstring's safety assumption ("the client can't choose/send the Gift Voucher mode") was **only
true if nothing ever put it in that list** — nothing enforced that. A cashier could pick "Gift
Voucher" as the mode, type any amount, and submit — no real voucher checked or consumed, GL entry
lands in the Gift Voucher account instead of Cash. This is a clean till-skimming vector: take real
cash, mark it paid by a nonexistent voucher.

**Fixed with two layers, keep both — neither alone is sufficient:**
1. `gift_voucher/events.py:validate_pos_profile_no_manual_gift_voucher_payment` (POS Profile
   `validate` hook, alongside `validate_pos_profile_cost_center`) — throws if "Gift Voucher" ever
   appears in a POS Profile's `payments` child table again.
2. **Defense in depth in `offline_pos/api.py:_validate_and_set_payments`** — explicitly rejects
   `mode_of_payment == "Gift Voucher"` in client-submitted payment rows, unconditionally, not
   just by relying on it being absent from `allowed_modes`. This is the one that actually matters
   if the POS Profile guard is ever bypassed (Desk UI isn't the only way to edit a POS Profile).

If a future report says "a payment mode is producing wrong GL entries" or "till doesn't
reconcile," check whether a server-only mode of payment (this one, or any future equivalent) has
ended up in a POS Profile's payment list before assuming it's a calculation bug.

## Client-side: no browsable voucher list — redemption requires the actual code

Also fixed 2026-07-16: the Benefits (F7) dialog used to fetch and list a selected customer's
gift vouchers as clickable buttons that auto-filled the code field — convenient, but it meant a
cashier only had to have a customer *selected* (by name/phone, not physically present) to browse
and redeem their vouchers. `loadCustomerBenefits()`/`renderGiftVoucherList()` in
`Posapplication/src/renderer/renderer.ts` no longer fetch or display a customer's voucher list at
all — redemption only works if whoever's at the counter provides the actual code (typed, or
scanned via a barcode-generated-from-`voucher_code` if the store's existing item scanner is
reused for this — not yet built, `voucher_code` is currently plain text with no barcode/QR
representation). Don't reintroduce a "browse this customer's vouchers" convenience feature
without a real proof-of-possession requirement behind it.

## Known cross-cutting quirk — don't silently "fix" it here

`fbr_pos/payload_builder.py:get_payment_mode()` picks the FBR-reported `PaymentMode` from
whichever payment row has the largest amount. A large gift-voucher redemption can become that
largest row and get mis-reported as the fallback default payment mode instead of the actual
cash/card portion paid. This is a known, flagged issue owned by the `fbr-integration` skill/
CLAUDE.md's "Known issues" section — if you touch it, update both that section and this one, not
just one.

## Where the code lives

- Doctypes: `aimatic/aimatic/doctype/gift_voucher_criteria/`, `.../gift_voucher/` (under the main
  Aimatic module, no separate Module Def).
- `aimatic/loyalty/` (`item_group_rate.py`, `events.py`), `aimatic/gift_voucher/`
  (`code_generator.py`, `events.py`, `api.py`).
- Patches: `patches/create_item_group_loyalty_custom_fields.py` (Item Group custom fields),
  `patches/create_gift_voucher_mode_of_payment.py` (Mode of Payment master — still needs a
  per-Company GL account set up manually before use, same as Cash/Card).
- Shared: `_returned_qty_by_row` lives in `aimatic/pos_shared.py` so both `offline_pos` and
  `loyalty/events.py` (correcting a returned invoice's points) use identical returned-quantity
  logic — don't reimplement this locally in either module.

## Working safely

- Before changing bracket/rate logic, re-check whether the change affects FBR-reported totals —
  anything touching how a voucher/point interacts with `grand_total`/`net_total` needs the same
  scrutiny as a `fbr_pos` change (see the `fbr-integration` skill).
- Update the `gift_voucher/`/`loyalty/` section of this bench's `CLAUDE.md` in the same session
  if a bracket rule, redemption mechanic, or the FBR-interaction contract changes.
