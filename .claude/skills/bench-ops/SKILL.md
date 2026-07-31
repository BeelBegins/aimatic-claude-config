---
name: bench-ops
description: Use for sites, backups, restore, migrate, build, restart, workers, scheduler, nginx or Caddy, HTTPS headers, new-site setup, deployment, imports, and any environment-sensitive operation. Always verify the current site role.
---

# Bench and site operations

Read `../../reference/current-state.md`, then verify the exact site, role,
configuration, branch/commit, processes, and intended impact read-only. Never
infer production or test status from a site name.

## Live-operation gate

Read-only diagnosis is allowed. Before any live mutation, migration, restore,
import, deployment, impactful restart, proxy change, scheduled job, data repair,
or destructive test:

1. obtain explicit approval for the exact target and action;
2. take the appropriate current backup and verify completion/recoverability;
3. state expected effects and narrow post-action checks;
4. prepare a concrete rollback path;
5. execute only the approved scope and record results.

Do not treat an old backup, a command preview, or another site's backup as
sufficient.

## Diagnose and verify

Inspect common and site configuration without exposing secrets. For HTTPS-only
authorization failures, verify the full forwarded-scheme/header chain before
changing business logic. Distinguish code deployment, schema migration, asset
build, cache clear, web-worker reload, queue-worker restart, and scheduler state;
run only what the change requires.

Afterward, verify process health and the specific business behavior, schema,
asset, job, or route affected. Report commit, target, backup identifier, actions,
checks, and rollback readiness. Update `current-state.md` only when a current
operational fact was actually verified and changed.
