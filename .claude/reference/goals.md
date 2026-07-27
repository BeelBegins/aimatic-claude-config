# Project goals and acceptance signals

Owner: user. Last reviewed: 2026-07-28. Agents may report evidence and propose
changes; they must not silently mark business goals complete or invent goals.

## G1 — safe production transition

Move SZL from preparation to real production without losing legacy data or
migration knowledge. Acceptance requires approved cutover scope, verified
backups/rollback, reconciled master/opening/stock/pricing totals, tested critical
flows, recorded deployment evidence and explicit user sign-off.

## G2 — dependable retail operation

Keep the roughly 2,000-transaction/day POS reliable across sale/refund,
payment, shift, offline retry/idempotency, price, receipt, FBR, stock/GL,
permission and recovery paths. Acceptance is evidence-based; absence of a bug
report is not proof.

## G3 — maintainable local-first development

Local code remains the immediate source of truth and Git the durable shared
history. Every module/migration/product has an owner, current facts are dated,
known issues are indexed, and coherent fixes are committed/pushed promptly.

## G4 — efficient multi-agent guidance

Claude and Codex share compact routers, task-triggered skills, code-adjacent
rules and lossless references. Targets:

- root fixed context under 200 lines per repository;
- all critical domains route to an owning skill/reference;
- 100% recall of production/POS/release safety in the 40-case contract;
- no literal secrets or stale environment claims in current-facing guidance;
- all legacy migration scripts/runbooks remain inventoried in Git.

Review these goals after cutover, a major product/release change, or a material
incident. Put task-level priorities in `priorities.md`, not here.
