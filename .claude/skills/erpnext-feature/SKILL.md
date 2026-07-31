---
name: erpnext-feature
description: Use for general aimatic features, DocTypes, hooks, doc_events, Custom Fields, Property Setters, fixtures, patches, or owned business logic that is not covered by a narrower domain skill. Never modify Frappe, ERPNext, or HRMS core.
---

# ERPNext features in aimatic

Put all owned behavior in `apps/aimatic`. Never edit `apps/frappe`,
`apps/erpnext`, or `apps/hrms` directly. Before adding logic, inspect
`aimatic/hooks.py`, existing controller methods, hooks, fixtures, and patches for
the same doctype.

## Lifecycle and authority

- Choose the earliest necessary event, not the most familiar one. Core
  controller `validate()` runs before app `validate` hooks; use
  `before_validate` when owned defaults must exist before core validation.
- Make server behavior authoritative. Client scripts may guide input but cannot
  be the only validation, permission, pricing, stock, or accounting control.
- Preserve all existing handlers and their ordering when multiple modules share
  a doctype event.

## Branch and accounting context

Reuse `branch_management.events.apply_branch_defaults` and current helpers.
Do not introduce generic warehouse or cost-center fallback. Set row-level
warehouse, branch, and cost center where the transaction controller reads rows;
parent defaults alone may not reach GL or stock entries. Keep deliberately
excluded POS flows server-owned by their POS Profile contract.

## Fixtures and patches

- Track Custom Field, Property Setter, Client Script, Server Script, permission,
  Workspace, and other configured records through the existing fixture/module
  mechanism. Export only the affected fixture and review the resulting diff.
- Place one-off patches in `aimatic/patches/` and register them once in
  `patches.txt`: pre-model sync only when no new schema is required; otherwise
  post-model sync.
- Make patches idempotent and narrowly scoped. Fresh install may mark historical
  patches complete without executing them, so put required baseline setup in the
  install path as well as upgrade repair when necessary.

## Verify narrowly

Run syntax/static checks and validate changed JSON or embedded script first.
Then test one normal path and the relevant denial, return, cancel, or retry path.
Run `bench build --app aimatic` only for affected public assets. Any migrate,
fixture export against a site, or deployment requires `bench-ops` and the
appropriate operation gate.
