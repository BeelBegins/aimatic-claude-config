---
name: bench-ops
description: Use for sites, backups, bench migrate/build/restart, workers, nginx/Caddy, HTTPS headers, new-site setup, deployment, scheduled site jobs, or any environment-sensitive operation. Always verify current site role; never rely on an old production/test label.
---

# Bench and site operations

Read `../../reference/current-state.md` first. Site role is verified runtime
state, not a permanent property of `szl`, `siezal`, or `hsm`.

## Production gate

Read-only diagnosis is allowed. A live mutation, migrate, restore, import,
deploy, restart with impact, proxy change, data refresh, or destructive test
requires all of:

1. explicit approval for the exact site/action;
2. a current appropriate backup and confirmation it completed;
3. expected effects and post-action verification;
4. a rollback path;
5. narrow execution with recorded results.

SZL was designated future production and not live when confirmed on
2026-07-28; re-verify before every impactful operation.

## Routine diagnosis

- Inspect `sites/common_site_config.json`, the target site's config, process
  state and proxy config without exposing credentials.
- For HTTPS-only validation failures, check the Caddy -> nginx forwarded
  scheme/header chain before changing business logic.
- Python code changes generally need the relevant workers restarted after
  code is deployed; migrate/build alone is not always sufficient.
- Use safe static/local tests freely, but do not run destructive or live suites
  without the gate.

## Historical procedures

The previous site map, proxy incident detail, commands and new-site checklist
are retained in
`references/historical-site-operations.md`. They are useful operational
history, not authorization and not proof of current environment role. Read the
specific section needed, verify every target/path, then apply the production
gate.

## Handoff

Record the exact commit, target site, backup identifier, commands/actions,
verification evidence and rollback status. If a durable site fact changed,
update `../../reference/current-state.md` with date and evidence.
