---
name: fbr-integration
description: "Use for Pakistan FBR POS e-invoicing: payload_builder, tax_calculator, accounting reconciliation, FBR Integration Settings, sandbox/production submission, custom_fbr fields, payment mode, or FBR Tax Category."
---

# FBR e-invoicing

Start in `aimatic/fbr_pos/`: `payload_builder.py`, `tax_calculator.py`,
`accounting.py`, `api.py`, settings via `settings.get_fbr_settings`.

## Gotchas

- Credentials stay in `FBR Integration Settings` (company+branch). Never log,
  fixture, or return tokens.
- Every Item needs `custom_fbr_tax_category` — blank hard-throws at POS submit.
- Build from server snapshots, not client-trusted tax/identity/payment values.
- Pakistan-localization Customer columns (`tax_strn`/`tax_ntn`/`tax_nic`) are
  optional per site. Check columns exist before selecting; fall back to
  `Customer.tax_id` for NTN.
- Clear copied `custom_fbr_*` on returns so each return submits independently.
- Inclusive GST lives in Sales Taxes and Charges; re-run totals. POS fee is
  sales-only. Align cash to the new grand total only where return rules allow.
- Voucher redemption is a payment row, not a discount (protects FBR item value).
  Largest-row payment-mode selection can misreport when a voucher dominates —
  see `known-issues.md`.
