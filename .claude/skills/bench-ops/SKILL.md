---
name: bench-ops
description: Bench and site operations — adding a new site, editing nginx/Caddy reverse-proxy config, backups, bench migrate/build/restart, or any change to production sites szl/siezal/hsm. Use whenever HTTPS-only checks break unexpectedly, a new site is being added, or before making any change to the production siezal site.
---

# Bench / site operations

## Site map

- `szl` — default site (`common_site_config.json`), used for testing. Port 8080.
- `siezal` — **production** (Company "Siezal Super Market"). Port 8081.
- `hsm` — Company "Hatim Super Market", currently used to prep/rehearse legacy-data migration
  scripts before they run for real elsewhere. Port 8082.

All three run the same `aimatic` codebase with separate data.

## Backup discipline

Before any change to a production site (`siezal` today; `hsm` once live), take a backup first:
`bench --site <site> backup`.

## The recurring nginx/HTTPS regression — check this first for HTTPS-check failures

Request path: **Caddy** (public TLS, one `reverse_proxy` block per site) → this bench's own
**nginx** (`config/nginx.conf`, symlinked to `/etc/nginx/conf.d/frappe-bench.conf` — editing
the repo file *is* editing the live config) → gunicorn.

Each site's `location @webserver` block **must** set
`proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;` (passing through Caddy's already-
correct value) — **not** nginx's generated default
`proxy_set_header X-Forwarded-Proto $scheme;`, which reflects only the Caddy→nginx hop (always
plain HTTP) and overwrites Caddy's correct value.

**This regresses on its own.** Any site-add (`bench setup nginx`) or other tool touching nginx
config regenerates `config/nginx.conf` and silently reverts every site's block back to
`$scheme`. Symptom signature to recognize immediately: POS **cashier** login works fine, POS
**administrator/Settings** login fails with "HTTPS is required for supervisor authorization" —
that exact pattern means this bug (see `offline-pos` skill for why admin auth specifically is
HTTPS-gated and cashier login isn't).

Fix: after any site-add or nginx-config change, grep for `X-Forwarded-Proto \$scheme` in
`config/nginx.conf` and re-apply the `$http_x_forwarded_proto` fix to every server block found.
Reloading (`sudo nginx -t && sudo systemctl reload nginx`) needs a real privileged terminal —
this cannot be done from a sandboxed/non-TTY session; ask the user to run it themselves.

## Standard commands

```bash
bench start                                       # web, socketio, watch, schedule, workers
bench --site <site> migrate                       # apply pending doctype/patch changes
bench --site <site> console                       # python shell with frappe context
bench build --app aimatic                         # rebuild JS/CSS after public/ changes
bench --site <site> export-fixtures --app aimatic # sync Desk customizations into git
bench --site <site> backup                        # before any production change
```

## Do not run the test suite

Never run `bench run-tests` — the user runs tests themselves. `offline_pos/test_api.py` is the
only test module; `apps/aimatic/.github/workflows/ci.yml` (`bench --site test_site run-tests
--app aimatic` against a throwaway site) is the reference for how tests *would* be invoked, not
something to run locally.

## New-site checklist

1. Add the site, install apps in order: `frappe`, `aimatic`, `erpnext`, `hrms`.
2. Assign the next port, add its nginx block + a Caddy `reverse_proxy` block.
3. Immediately check/fix the `X-Forwarded-Proto` gotcha above — don't wait for a symptom.
4. If this is a legacy-data cutover from the old iPOS software, hand off to the
   `ipos-migration` skill for the item/supplier import workflow.

Update the "Reverse proxy" and "Repository overview" sections of the top-level `CLAUDE.md` in
the same session if the site list, ports, or the nginx fix procedure change.
