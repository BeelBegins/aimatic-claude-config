---
name: fbr-integration
description: Pakistan FBR e-invoicing work on POS Invoice — payload_builder, tax_calculator, accounting reconciliation, FBR Integration Settings (sandbox/production tokens), custom_fbr_* fields, or FBR Tax Category. Use whenever FBR submission, e-invoicing payload, or FBR tax rate/category comes up.
---

# FBR e-invoicing integration (fbr_pos)

## Module map

`apps/aimatic/aimatic/fbr_pos/`:
- `payload_builder.py` — builds the FBR submission payload from a POS Invoice, snapshotting
  item/tax/customer data onto `custom_fbr_*` fields.
- `api.py` — submits the payload; sandbox/production URL and credentials come from
  `FBR Integration Settings`, keyed by company+branch, loaded via `settings.py:get_fbr_settings`.
- `tax_calculator.py` — computes FBR-specific tax amounts per line.
- `accounting.py` — reconciles the FBR tax/fee back into the invoice's own Sales Taxes and
  Charges table (`add_fbr_sales_tax_row` for inclusive GST via an effective rate so customer
  price doesn't change; `add_fbr_pos_fee_row` for the extra Rs. fee on sales only, never
  returns), re-triggers `calculate_taxes_and_totals`, then aligns cash payment to the new grand
  total (`adjust_cash_payment_to_grand_total`, skipped for returns).

## Hard requirements

- `Item.custom_fbr_tax_category` is mandatory in practice —
  `tax_calculator.py:get_item_fbr_configuration()` hard-throws at POS submit time if it's
  blank. Any new item-creation path (imports, bulk creation) must set this or fall back to the
  `"Exempt goods"` category, matching `patches.create_item_fbr_tax_rate_field`'s precedent.
- Returns clear the copied `custom_fbr_*` snapshot fields
  (`events.py:clear_copied_fbr_fields_for_return`) so a refund submits to FBR independently
  rather than inheriting the original sale's FBR state — don't "simplify" this by copying
  snapshot values forward.
- Never log or expose `FBR Integration Settings.security_token` or credentials client-side —
  they're loaded server-side only via `settings.py`.

## Known open issue (flagged, not fixed — don't silently "fix" it as a side effect)

`get_payment_mode()` picks the e-invoicing `PaymentMode` field from whichever payment row has
the largest amount, then matches "cash"/"card" in its name, else falls back to
`FBR Integration Settings.default_payment_mode`. Gift Voucher redemption is its own Mode of
Payment row — if it's the largest row on a sale (e.g. a big voucher covering most of the
bill), FBR gets the fallback default instead of the actual cash/card portion paid. Not a
crash, just a misreported field on that subset of sales.

## Working safely

- Test against **sandbox** `FBR Integration Settings` before touching production
  URL/credentials — this integration talks to a real government e-invoicing endpoint.
- Before considering a payload/tax/accounting change safe, verify the built payload and
  resulting Sales Taxes and Charges rows against a known-good invoice's expected values, not
  just "it didn't crash."
- Update the `fbr_pos` section of the top-level `CLAUDE.md` in the same session if payload
  fields, accounting reconciliation logic, or the known-issue list changes.
