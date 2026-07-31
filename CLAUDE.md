# Ai Matic development guide

Use this file only as the project router. Load the smallest matching skill and
inspect current code instead of copying implementation detail into guidance.

## Authority

When sources disagree, prefer:

1. current local code, configuration, and uncommitted diff;
2. verified read-only runtime state;
3. active guidance in `.claude/`.

Never overwrite an unfamiliar local change. Read `current-state.md` before
environment-sensitive work, `priorities.md` before choosing work, and `goals.md`
when acceptance criteria are unclear.

## Safety

- Verify the role and state of every site read-only. A site name is not proof
  that it is production, test, live, or inactive.
- Read-only diagnosis is allowed. Any live mutation, migration, deployment,
  impactful restart, destructive test, import, or data repair requires explicit
  approval, a current verified backup, a verification plan, and a rollback path.
- The retail POS handles roughly 2,000 transactions daily. Preserve cashier
  flow, offline/idempotency behavior, pricing, payments, stock, GL, FBR,
  permissions, and audit trails.
- Never place credentials, tokens, private keys, or database passwords in code,
  guidance, fixtures, logs, commits, or prompts. OAuth public clients use PKCE
  and have no client secret.
- Do not modify Frappe, ERPNext, or HRMS core. Put owned changes in
  `apps/aimatic/` or `/home/nabeel/Posapplication`.
- Run safe local static checks and targeted tests. Expand verification only
  when risk or a failure justifies it; never run live or destructive suites
  without the production gate.
- Every push to Posapplication `main` publishes all products. Keep unreleased
  work, including guidance-only changes, on a non-release branch.

## Route before editing

Load one primary skill by default; load a second only when the requested change
actually crosses ownership boundaries.

- `ipos-migration`: legacy imports, opening data, cutover, SZL setup.
- `purchase-cycle`: purchase documents, returns, taxes, offers, landed cost.
- `shelf-pricing`: branch, MRP, and Foodpanda selling-price propagation.
- `offline-pos`: Electron POS API, cashiers, shifts, sales, refunds, permissions.
- `oauth-client-surfaces`: POS/Sales/Shopping/Restaurant client authentication
  and server contracts.
- `fbr-integration`: FBR payloads, tax, submission, and reconciliation.
- `foodpanda-integration`: Foodpanda Partner API auth, catalog/outlet sync,
  and order webhooks.
- `loyalty-gift-voucher`: earning, issuance, and redemption.
- `ai-assistant-console`: governed AI tools, models, responses, and dashboards.
- `sql-reconciliation`: ledger analytics, valuation, and reconciliations.
- `bench-ops`: sites, backups, proxy, workers, migrate, and deploy.
- `erpnext-feature`: general aimatic hooks, DocTypes, fixtures, and patches.
- `print-format-packaging`: print formats, reports, layouts, and rendering.
- `desk-navigation`: Workspaces, sidebars, and Page routes.
- `posapplication-release`: any Posapplication build, version, push, CI run,
  APK/AAB/Windows/web artifact, or publication request.

Use `module-catalog.md` for ownership and `known-issues.md` only for active risk.

## Repositories and workflow

- Guidance/config: `/home/nabeel/frappe-bench`
- ERP app: `/home/nabeel/frappe-bench/apps/aimatic`
- Client apps: `/home/nabeel/Posapplication`

Before editing, inspect status, branch, and the relevant local diff in each
repository in scope. Inspect Git history only when it answers a specific
question. Preserve unrelated changes.

For a release-only Posapplication request, follow the cutoff fast path in
`posapplication-release`: concise status/stat and staged-file checks, one
intentional versioned push, concise CI monitoring, failed logs only, and final
asset verification.

Run `scripts/audit_ai_guidance.py` after guidance edits. Update active guidance
only when routing, ownership, a safety invariant, current state, or an unresolved
risk would otherwise become wrong. Git is the sole historical record.
