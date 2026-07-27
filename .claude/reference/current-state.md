# Current operational state

Last human-confirmed: 2026-07-28 (Asia/Karachi).

This file records current claims only. Verify read-only before any
environment-sensitive action and update the date/evidence when facts change.

## Sites

- `szl`: designated future production site; setup/data preparation was in
  progress and it was not yet live when confirmed.
- `siezal`: source site for the SZL catalog/setup work and historical live
  operating data. Do not assume it remains the live endpoint after cutover.
- `hsm`: separate configured site. Verify its role and data before changes.

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
