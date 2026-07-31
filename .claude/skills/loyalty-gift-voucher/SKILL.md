---
name: loyalty-gift-voucher
description: Use for item-group-weighted loyalty points, Loyalty Point Entry correction, Gift Voucher Criteria, issuance, validation, redemption, Benefits flow, or gift_voucher_code behavior in POS preview and submission.
---

# Loyalty and gift vouchers

Inspect `aimatic/loyalty/`, `aimatic/gift_voucher/`, the POS submit path, and all
POS Invoice hooks before changing event behavior. Multiple handlers share submit
and cancel events.

## Loyalty

Reuse ERPNext's Loyalty Program and ledger. Keep only the earning-rate override
custom: resolve the nearest configured Item Group ancestor and preserve the
difference between “inherit” and an explicit zero rate. Correct ERPNext's created
Loyalty Point Entry in place after submit, including returns. Keep the Item Group
Hierarchy report consistent with the effective-rate rule.

## Voucher rules

- Match issuance criteria by exact company and branch. Keep the redemption
  minimum independent from the issuance bracket floor.
- Issue on submit and redeem by code on a later sale. Excess value is forfeited;
  do not invent a remaining-balance or automatic same-sale redemption flow.
- Compute a new voucher's bracket and amount from invoice value net of same-sale
  voucher and loyalty redemption, while leaving FBR-facing invoice totals intact.
- Represent redemption as the server-created `Gift Voucher` payment row, never a
  discount. Do not add it to POS Profile payment choices.
- Reject manually submitted Gift Voucher payment rows unconditionally and retain
  the POS Profile validation that blocks this mode. Both controls are required.
- Consume a voucher with a conditional active-status update only after invoice
  submission succeeds, inside the transaction/savepoint used for POS idempotency.
  A failed or retried sale must not burn or double-consume it.
- Require online server validation. Never estimate, queue, or redeem a voucher
  during an offline sale. Require possession of the code; do not expose a
  browsable customer voucher list to cashiers.

## FBR interaction and verification

Keep voucher value in payments so FBR item values are not reduced. If mixed
payment-mode reporting changes, also use `fbr-integration` because that crosses
ownership.

Test the smallest affected path: effective loyalty rate or return correction;
voucher bracket boundaries; successful, invalid, already-used, concurrent, and
replayed redemption; cancel behavior; and offline rejection. Reconcile the
invoice payment rows, voucher status, loyalty ledger, and FBR-facing totals.
