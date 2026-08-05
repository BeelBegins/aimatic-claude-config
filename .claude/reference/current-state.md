# Current operational state

Last human-confirmed: 2026-08-05 (Asia/Karachi).
Verified backup before Foodpanda SFTP schedule-time field migrate on `szl`:
`20260805_204347-szl` (db gunzip ok). Prior SFTP schema migrate backup:
`20260805_201451-szl` (db gunzip ok). Prior POS API reload backup:
`20260805_045249-szl` (db gunzip ok).
Posapplication release `v3.0.14` published (refund step-up + related POS fixes).

This file records current claims only. Verify read-only before any
environment-sensitive action and update the date/evidence when facts change.

## Sites

- `szl`: production/live site (user-confirmed 2026-08-04). Canonical target for
  REST development and release verification — still verify before mutations.
- `siezal`: testing/development (confirmed 2026-07-31). Serves `aimatic.tech`
  with real historical data; verify before high-impact changes. Foodpanda schema
  migration verified 2026-08-01 at aimatic `14999fa` (backup
  `20260801_001900-siezal`).
- `hsm`: testing/development (confirmed 2026-07-31). Serves `hsm.aimatic.tech`;
  verify before high-impact changes.

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
