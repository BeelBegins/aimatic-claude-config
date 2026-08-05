---
name: loyalty-gift-voucher
description: Use for item-group-weighted loyalty points, Loyalty Point Entry correction, Gift Voucher Criteria, issuance, validation, redemption, Benefits flow, or gift_voucher_code behavior in POS preview and submission.
---

# Loyalty and gift vouchers

Inspect `aimatic/loyalty/`, `aimatic/gift_voucher/`, and all POS Invoice submit/
cancel hooks — multiple handlers share those events.

## Gotchas

- Loyalty reuses ERPNext's ledger. Only earning-rate override is custom: nearest
  configured Item Group ancestor; distinguish inherit vs explicit zero. Correct
  ERPNext's Loyalty Point Entry in place after submit (including returns).
- Issuance matches exact company+branch. Redemption minimum ≠ issuance floor.
- Issue on submit; redeem by code on a later sale. Excess value is forfeited —
  no remaining-balance or same-sale auto-redemption.
- Bracket amount uses invoice value net of same-sale voucher/loyalty redemption;
  FBR-facing item totals stay intact.
- Redemption is a server-created `Gift Voucher` payment row, never a discount.
  Reject client-supplied Gift Voucher payment rows; keep it off POS Profile
  tender choices.
- Consume with conditional active-status update only after submit succeeds,
  inside the POS idempotency transaction. Failed/retried sales must not burn or
  double-consume.
- Online validation only — no offline estimate/queue/redeem; no browsable
  cashier voucher list.
