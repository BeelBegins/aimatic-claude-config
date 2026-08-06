---
name: erpnext-feature
description: Use for general aimatic features, DocTypes, hooks, doc_events, Custom Fields, Property Setters, fixtures, patches, or owned business logic that is not covered by a narrower domain skill. Never modify Frappe, ERPNext, or HRMS core.
---

# ERPNext features in aimatic

Owned code lives in `apps/aimatic` only. Inspect `hooks.py`, existing handlers,
fixtures, and patches for the same doctype before adding logic.

## Gotchas

- Core `validate()` runs before app `validate` hooks. Use `before_validate` when
  owned defaults must exist before core validation can reject the doc.
- Client scripts guide input; server hooks own validation, permissions, pricing,
  stock, and accounting.
- Preserve handler order when multiple modules share a doctype event.
- Reuse `branch_management.apply_branch_defaults`. No generic warehouse or
  cost-center fallback. Set row-level warehouse/branch/cost_center — parent
  defaults often do not reach GL/stock. POS Invoice stays POS-Profile-owned.
- Fixtures use the exclude-list in `fixture_exclusions.json`. A second
  `Custom DocPerm` fixture block needs its own `"prefix"` or it clobbers the
  shared output file.
- `Item Price.custom_barcodes` is owned by `aimatic.item_pricing.barcodes` —
  keep field, hooks, fixture, and backfill patch in sync.
- Patches are idempotent; register once in `patches.txt`. Fresh install may skip
  historical patches, so baseline setup also belongs in the install path.
