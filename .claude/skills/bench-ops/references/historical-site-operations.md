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

## Python code changes need a worker restart, not just migrate/build

This bench's gunicorn runs `--preload` (`ps -eo cmd | grep gunicorn` shows it; supervisor program
`frappe-bench-frappe-web`) — the whole app is imported **once** in the master process before
forking all workers, and every worker shares that preloaded module state. `bench --site <site>
migrate` (schema) and `bench build`/`clear-cache` (JS/CSS/Redis) do **not** touch this — a new or
changed Python function (a new whitelisted API method, a modified doc_event handler, anything)
is invisible to already-running workers until they're restarted, even though `bench --site <site>
execute <path>` (which spawns its own fresh process) sees it immediately. Symptom: a function you
just added/edited works when called directly via `bench execute` but the live site 500s with
`AttributeError: module '...' has no attribute '...'` or silently keeps old behavior when hit
over HTTP. Confirmed live 2026-07-18 adding new `aimatic.ai.api` endpoints.

Fix: `sudo supervisorctl restart frappe-bench-frappe-web` — needs a real privileged terminal,
same as the nginx reload above; ask the user to run it themselves. `bench restart` fails the same
way (`sudo supervisorctl status` under the hood) unless run somewhere with passwordless sudo.
Always deploy Python changes as: edit → (`migrate` if schema changed) → **restart the web
worker** → re-verify against the live site, not just via `bench execute`.

## Do not run the test suite

Never run `bench run-tests` — the user runs tests themselves. `offline_pos/test_api.py` is the
only test module; `apps/aimatic/.github/workflows/ci.yml` (`bench --site test_site run-tests
--app aimatic` against a throwaway site) is the reference for how tests *would* be invoked, not
something to run locally.

## Scheduled szl refresh from siezal (dev/test data sync)

`szl` is periodically overwritten with a full copy of production `siezal` (database + files) so
testing happens against realistic data. Script: `scripts/refresh_szl_from_siezal.sh` (not
git-tracked — frappe-bench itself isn't a git repo). Runs via user crontab (`crontab -l`) at
08:00 and 20:00 daily, plus on demand: `bash scripts/refresh_szl_from_siezal.sh`. Logs to
`logs/refresh_szl_from_siezal.log`; uses `flock` (`logs/refresh_szl_from_siezal.lock`) so an
on-demand run and the scheduled one can't overlap.

Pipeline: `bench --site siezal backup --with-files --compress` → sync `encryption_key` onto szl
→ `bench --site szl restore <db> --with-public-files <pub> --with-private-files <priv> --force`
→ `bench --site szl migrate` + `clear-cache` → prune siezal backups older than 7 days.

**This completely overwrites szl's database and files every run, by design** — any szl-only test
data present at run time is destroyed. Also overwrites szl's Administrator password and every
site-level credential (integration secrets, FBR tokens) with siezal's. siezal's `FBR Integration
Settings` currently point at **Sandbox**, not Production, which is why this is safe today — if
siezal's FBR environment is ever switched to Production, re-check whether szl needs a guard so
test activity there can't submit real e-invoices under production FBR credentials.

Two gotchas discovered building this (2026-07-20), both non-obvious and worth knowing before
touching this script or the restore flow generally:

- **`bench restore` needs the MariaDB root password** (to drop/recreate the target database
  before importing) and prompts interactively via `getpass` if it isn't supplied — which hangs
  forever under cron with no TTY. `frappe.database.mariadb.setup_db.get_root_connection` checks
  `frappe.conf.get("mariadb_root_password")` / `frappe.conf.get("root_password")` *before*
  prompting, so the fix is storing it in `sites/common_site_config.json` as `"root_password"`
  (bench-wide, same file that already holds `openrouter_api_key`) rather than passing
  `--db-root-password` on the CLI. Because that file now holds two plaintext secrets, it's
  `chmod 600` (owner-only) — a permissions change from its previous `664`; don't let a future
  `bench` operation silently loosen it back.
- **Restoring one site's DB backup onto a different site requires syncing `encryption_key`
  too, and the timing matters.** Each site's `site_config.json` has its own independent
  `encryption_key` (confirmed different between szl and siezal); Password-type fields (e.g. `FBR
  Integration Settings.security_token`) are encrypted with the *site's* key, so a restored DB
  full of siezal-encrypted values is undecryptable under szl's own key. The script runs `bench
  --site szl set-config encryption_key <siezal's key>` *before* the restore. This means if the
  restore step itself then fails or is interrupted, szl is left in a broken intermediate state —
  new config key, but still its own old data underneath — until the script completes
  successfully. Confirmed live: an interrupted first run (root-password prompt hanging) left szl
  in exactly this state; recovery was setting szl's `encryption_key` config back to its own prior
  value (visible in git-untracked `site_config.json`, or recoverable from any recent
  `sites/szl/private/backups/*-site_config_backup.json`) until the script could be re-run clean.
  If this script ever fails mid-run, check `sites/szl/site_config.json`'s `encryption_key` before
  assuming szl is still in a good state.

## New-site checklist

1. Add the site, install apps in order: `frappe`, `aimatic`, `erpnext`, `hrms`.
2. Assign the next port, add its nginx block + a Caddy `reverse_proxy` block.
3. Immediately check/fix the `X-Forwarded-Proto` gotcha above — don't wait for a symptom.
4. If this is a legacy-data cutover from the old iPOS software, hand off to the
   `ipos-migration` skill for the item/supplier import workflow.

Update the "Reverse proxy" and "Repository overview" sections of the top-level `CLAUDE.md` in
the same session if the site list, ports, or the nginx fix procedure change.
