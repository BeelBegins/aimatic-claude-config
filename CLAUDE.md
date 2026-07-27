# Ai Matic development guide

This is the small, always-loaded project router. Detailed facts live in
task-specific skills and references so agents load them only when relevant.
Do not remove a fact merely to shorten guidance: move it to the owning skill
or a tracked reference and update the indexes.

## Authority and freshness

Use this order when sources disagree:

1. local code, configuration, and uncommitted diff;
2. verified read-only site/runtime state;
3. current tracked guidance in `.claude/reference/`;
4. task-specific skills in `.claude/skills/`;
5. dated/historical records;
6. remote Git state.

Local files are the development source of truth. Git is the durable shared
history and should be pushed after fixes, coherent work sessions, or at least
daily/weekly. Never discard or overwrite an unfamiliar local change.

Read `.claude/reference/current-state.md` before environment-sensitive work.
Read `.claude/reference/priorities.md` before choosing what to work on.
Use `.claude/reference/goals.md` for outcome and acceptance criteria.
Agents may propose priority edits but must not silently change priorities.

## Non-negotiable safety

- `szl` is designated for production, but was prepared and not live when last
  confirmed on 2026-07-28. Verify current state read-only; never infer it from
  a site name or an old document.
- Read-only diagnosis is allowed. Any live mutation, migration, deployment,
  restart with impact, destructive test, or data repair requires explicit
  approval, a current backup, a verification plan, and a rollback path.
- The retail POS is business-critical and handles roughly 2,000 transactions
  daily. Preserve cashier flow, offline/idempotency behavior, pricing,
  payments, stock, GL, FBR, permissions, and audit trails.
- Never put credentials, private keys, tokens, or database passwords in code,
  guidance, fixtures, logs, commits, or prompts. OAuth public clients use PKCE
  and have no client secret.
- Do not modify Frappe, ERPNext, or HRMS core. Own changes in
  `apps/aimatic/` or `/home/nabeel/Posapplication`.
- Safe local static checks/builds are allowed. Do not run destructive or live
  suites, migrations, imports, or production-like data tests without approval.
- Never push Posapplication guidance directly to `main`: every push to
  `main` publishes all products. Use a non-release branch and merge only with
  an intentional versioned release.

## Route the task before editing

Load the matching skill under `.claude/skills/`:

- `ipos-migration`: legacy iPOS imports, cutover, opening data, SZL setup.
- `purchase-cycle`: purchase orders/receipts/invoices/returns, taxes, trade
  offers, landed cost, shelf and supplier pricing.
- `shelf-pricing`: Selling/Foodpanda price application and rollback.
- `offline-pos`: POS server API, shifts, payments, permissions, fresh-install
  terminal grants, and idempotency.
- `oauth-client-surfaces`: Android/Electron Sales, Shopping, Restaurant, POS.
- `fbr-integration`: fiscalization and FBR submission/failure behavior.
- `loyalty-gift-voucher`: loyalty and voucher issuance/redemption.
- `ai-assistant-console`: governed AI tools, dashboards, model calls, incidents.
- `sql-reconciliation`: financial/stock/reporting queries and reconciliation.
- `bench-ops`: sites, backups, proxy, workers, migration/deployment operations.
- `erpnext-feature`: general aimatic DocTypes, hooks, fixtures, and patches.
- `print-format-packaging`, `desk-navigation`: their named surfaces.
- `posapplication-release` and `release-*-apk`: release-only workflows.

The full ownership map is `.claude/reference/module-catalog.md`. Known active
risks are indexed in `.claude/reference/known-issues.md`. Historical knowledge
from the former large root file remains losslessly archived in
`.claude/reference/project-knowledge-archive-2026-07-28.md`; treat its dated
environment/version claims as historical until verified.

## Repositories

- Bench/config guidance: `/home/nabeel/frappe-bench`
- ERP application: `/home/nabeel/frappe-bench/apps/aimatic`
- Client applications: `/home/nabeel/Posapplication`

Before work, inspect `git status`, branch, recent log, and relevant local diff
in every repository in scope. Commit by coherent behavior so regression
tracing remains useful. Run `scripts/audit_ai_guidance.py` before committing
guidance changes.

## Keep the system current

When development changes a durable fact:

1. update code and its closest runbook/reference;
2. update the owning skill if routing, invariants, or workflow changed;
3. update `current-state.md` only after verification;
4. add/remove the item in `known-issues.md`;
5. update `module-catalog.md` when ownership or entry points change;
6. preserve historical detail with a date instead of presenting it as current;
7. run the guidance audit and relevant code checks;
8. commit and push the local source of truth.

Private agent memory is for user preferences, personal tool hints, and
short-lived context—not project architecture, production facts, migrations,
or known issues. Durable project knowledge must remain in Git.
