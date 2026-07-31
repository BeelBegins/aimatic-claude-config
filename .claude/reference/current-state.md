# Current operational state

Last human-confirmed: 2026-07-31 (Asia/Karachi).

This file records current claims only. Verify read-only before any
environment-sensitive action and update the date/evidence when facts change.

## Sites

- `szl`: designated future production site; setup/data preparation was in
  progress and it was not yet live when confirmed.
- `siezal`: source site for the SZL catalog/setup work and historical live
  operating data. User-confirmed 2026-07-31 as testing/development, not
  production - still verify before high-impact changes since it responds
  live on `aimatic.tech` and carries real historical data. Foodpanda schema
  migration verified 2026-08-01 at aimatic commit `14999fa`, with pre-migration
  backup prefix `20260801_001900-siezal`.
- `hsm`: user-confirmed 2026-07-31 as testing/development. Responds live on
  `hsm.aimatic.tech` - verify current data/role before high-impact changes.

Site names do not grant permission or prove production status.

## Production gate

Read-only diagnosis is permitted. Before a live mutation or deployment:

1. obtain explicit user approval for the exact target/action;
2. take and verify a current backup appropriate to the change;
3. state expected effects and verification checks;
4. prepare a rollback path;
5. execute narrowly and record evidence/results.

## Repository truth

- Local worktrees are primary during active development.
- Push coherent commits after fixes/work sessions and no less frequently than
  the user's daily/weekly cadence.
- `/home/nabeel/Posapplication/main` is a release trigger for all products;
  guidance-only work must stay on a non-release branch.

## Critical workload

The retail POS processes roughly 2,000 transactions per day. Treat changes to
sale submission, payment, shift close, offline recovery, stock/GL posting,
pricing, FBR, and permissions as high risk.
