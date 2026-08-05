---
name: bench-ops
description: Use for sites, backups, restore, migrate, build, restart, workers, scheduler, nginx or Caddy, HTTPS headers, new-site setup, deployment, imports, and any environment-sensitive operation. Always verify the current site role.
---

# Bench and site operations

Read `../../reference/current-state.md`, then verify site role, config, and
impact read-only. A site name is not proof of production vs test.

## Live gate

Before any live mutation, migrate, restore, import, deploy, impactful restart,
proxy change, or destructive test: explicit approval, verified current backup,
expected checks, rollback path, then approved scope only.

## Gotchas

- Cashier login fine + supervisor auth broken usually means nginx overwrote
  `X-Forwarded-Proto` with `$scheme` instead of `$http_x_forwarded_proto`.
  `bench setup nginx` regenerates this; re-check after any site-add.
- Distinguish code deploy, migrate, asset build, cache clear, web-worker
  reload, queue-worker restart, and scheduler — run only what the change needs.
- Update `current-state.md` only when a verified operational fact changed.
