---
name: fbr-integration
description: "Use for Pakistan FBR POS e-invoicing: payload_builder, tax_calculator, accounting reconciliation, FBR Integration Settings, sandbox/production submission, custom_fbr fields, payment mode, or FBR Tax Category."
---

# FBR e-invoicing

Start in `apps/aimatic/aimatic/fbr_pos/`: `payload_builder.py` snapshots invoice
data, `tax_calculator.py` derives line tax, `accounting.py` aligns invoice tax
rows and payments, and `api.py` submits using server-loaded settings.

## Invariants

- Keep FBR URLs and credentials in `FBR Integration Settings`, selected by the
  current company and branch. Never log tokens, return them to a client, place
  them in fixtures, or include them in test output.
- Require a valid `Item.custom_fbr_tax_category` on every item-creation/import
  path. Use the existing exempt-category precedent only where current code does.
- Build payloads from server documents and snapshots, never from client-trusted
  tax, identity, payment, or invoice values.
- Clear copied `custom_fbr_*` snapshot state on returns so each return is
  calculated and submitted independently. Preserve original-document references;
  do not copy the sale's submission state forward.
- Keep inclusive GST reconciliation inside Sales Taxes and Charges and re-run
  ERPNext totals. Apply the POS fee only to sales, not returns. Align cash to the
  resulting authoritative total only where current return rules allow it.
- Treat voucher redemption as payment, not a discount, so item value reported to
  FBR remains intact. Account for the active largest-payment-mode limitation in
  `known-issues.md` when changing mixed payments.

## Verification

Use sandbox settings first. For one known document, compare the complete payload,
item tax values, invoice tax rows, grand total, payments, and stored response with
independently expected values. Include one return and one rejected/failed response
when those paths change. Confirm accounting and payload agree; a successful HTTP
response alone is insufficient. Production credentials or submission require the
full live-operation gate.
