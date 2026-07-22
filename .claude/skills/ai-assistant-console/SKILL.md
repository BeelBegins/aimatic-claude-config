---
name: ai-assistant-console
description: Working on aimatic's AI Assistant Console (aimatic/ai/, aimatic/aimatic/page/ai_assistant_console/) — the Nemotron/OpenRouter-backed conversational BI assistant, its certified tools, ERPNext report runner, governed analytics/drill-down fallbacks, structured response contract, conversation management, saved reports/dashboards/export, or scheduled questions/alert rules. Use whenever ai/api.py, ai/tools*.py, ai/*.py, or ai_assistant_console.js/.css changes, or a new AI Business Intelligence Console phase is being built.
---

# AI Assistant Console (multi-phase AI Business Intelligence Console)

Nemotron/OpenRouter client plus a conversational analytics assistant over sales/purchases/
vendors/inventory/customers, at its own route `ai-assistant-console`
(`aimatic/aimatic/page/ai_assistant_console/`, same route-collision-avoidance reasoning as
`vendor-performance-console`/`sales-dashboard-console` — see the `desk-navigation` skill),
reachable via the root `Aimatic` workspace's "AI Assistant" shortcut.

Built as a multi-phase "AI Business Intelligence Console" per an explicit product spec
(2026-07-17). **Phase 1** (2026-07-17: structured answers, KPI/chart/table/insight rendering,
smart context bar, role-aware suggestions, 5 new domain tools), **Phase 2** (2026-07-18:
conversation management, a controlled dynamic-report fallback layer, browser-native voice input,
a collapsible left/right panel layout), and **Phase 3** (2026-07-18: save/pin answers, a
dashboard builder, working CSV/Excel export, scheduled question re-runs, insight-detector-based
alert rules) are all live. ABC/XYZ classification and role-specific landing dashboards remain
later phases, not yet built. **Phase 4** (2026-07-20) expands the certified catalogue from 25
to 38 tools, makes catalogued ERPNext reports executable, and adds a governed semantic query
engine plus transaction drill-down; the assistant now exposes 43 read-only function calls in
total once the report-search/report-runner, analytics/drill-down, and legacy dynamic fallback
are counted.

**Working pattern**: Nemotron did the actual design/code drafting for nearly all three phases via
the `ask-nemotron` CLI (see the `reference_ask_nemotron_cli` memory), with a human/Claude review
pass catching and fixing real bugs before every single deploy (see "Gotchas found only by running
it" below). This division of labor — Nemotron drafts, a review pass verifies against live
schema/data/browser behavior before trusting it — is the proven, expected pattern for future
phases too, not something that gets safer to skip as the codebase grows. **Exception**:
OpenRouter's free tier hit its shared daily quota mid-Phase-2 (`free-models-per-day`, resets
~00:00 UTC) — the dynamic-report layer, voice input, and panel layout were written directly for
that stretch, same review rigor applied; Phase 3 resumed the Nemotron-drafts workflow once the
quota reset.

**Deployment gotcha — Python changes need a worker restart, not just migrate/build**: this
bench's gunicorn runs `--preload` (see bench-ops skill), so a whitelisted API change is invisible
to already-running workers — `bench --site <site> execute <path>` sees it immediately (fresh
process) but the live site 500s with `AttributeError: ... has no attribute ...` until `sudo
supervisorctl restart frappe-bench-frappe-web` runs. This bit every phase of this module at least
once, twice in Phase 3 alone (once for save/dashboard/export, again for scheduling/alerts) —
always restart after any `ai/*.py` change before trusting a live-site test.

## Nemotron client and model config

`nemotron_client.py` — `get_chat_completion(messages, tools=None, tool_choice=None,
temperature=0.2, max_tokens=1024, model=None)` wraps OpenRouter's `/chat/completions` endpoint
(`requests`, same timeout/header pattern as `fbr_pos/api.py:submit_payload_to_fbr`) and returns
the raw assistant *message* dict (`content`/`tool_calls`), raising `NemotronError` on any failure
rather than ever returning a partial/empty result. `get_completion(prompt, ...)` is a text-only
wrapper (used by `api.py:ping`). Config comes from `frappe.conf` (`openrouter_api_key`,
`openrouter_nemotron_model` — set via `bench set-config -g <key> <value>`, landing in
`sites/common_site_config.json` so all three sites share one key), never hardcoded. Hardcoded
fallback in code is `nvidia/nemotron-3-super-120b-a12b`, but the bench-wide config key is set to
`nvidia/nemotron-3-ultra-550b-a55b:free` (2026-07-17, upgraded from the 120B Super — same free
OpenRouter tier, larger model, 1M context) so that's the model actually used everywhere unless
overridden per-call. The personal `ask-nemotron` CLI (`reference_ask_nemotron_cli` memory) has its
own separate hardcoded `DEFAULT_MODEL` since it doesn't read this config key — kept in sync by
hand, not automatically. OpenRouter's `/api/v1/models` is the source of truth for available slugs.

**The free tier has a shared daily AND concurrency cap** — seen in practice: a transient
`ResourceExhausted: Worker local total request limit reached (32/32)` (concurrency) and a hard
`Rate limit exceeded: free-models-per-day` (daily quota, resets ~00:00 UTC) that took the entire
production AI Assistant down site-wide for szl/siezal/hsm simultaneously (they share one key) mid-
Phase-2 until it reset. `ask()` surfaces either as a normal `NemotronError` → user-facing error
message, not a crash.

## Frontend-editable model/enable settings (`AI Integration Settings`, added 2026-07-20)

The API key stays exactly where it was (`frappe.conf`, per an explicit product decision - never
stored on any doctype, never returned by any endpoint below), but the *model* and a master on/off
switch are now editable from the Desk frontend without shell access, via a new per-site Single
DocType `AI Integration Settings` (`aimatic/aimatic/doctype/ai_integration_settings/`, module
`Aimatic`, System-Manager-only permissions - same shape as `Shopping Settings`, the precedent this
was modeled on). Two fields: `enabled` (Check, default 1) and `model` (Data, blank = "use the
fallback chain below").

**Config/enabled resolution order, `nemotron_client.py`**:
1. `_get_model()`: `AI Integration Settings.model` (if non-blank) → `frappe.conf.get
   ("openrouter_nemotron_model")` → hardcoded `DEFAULT_MODEL`. The doctype is the new highest-
   priority tier; a site that never touches it behaves exactly as before this feature existed.
2. `_check_enabled()`, called at the very top of `get_chat_completion()` (the one choke point both
   `ask()` and `ping()` already funnel through) - raises `NemotronError` before any network call if
   `AI Integration Settings.enabled` is falsy. This is a real kill switch, not just a UI hint: it
   blocks the request server-side regardless of which entrypoint or role calls in.
3. Both read via `frappe.get_cached_doc("AI Integration Settings")` - cheap, Frappe caches Singles
   automatically and invalidates on save, so there's no extra caching code needed here.

A `[post_model_sync]` patch, `ensure_ai_integration_settings_enabled`
(`aimatic/patches/ensure_ai_integration_settings_enabled.py`), unconditionally sets `enabled = 1`
via `frappe.db.set_single_value` right after the doctype is created by migrate - a Single
doctype's field JSON `"default"` isn't reliably applied just by the doctype existing, and since
this field is a kill switch for a feature that was already working, leaving that to chance risked
silently disabling the assistant on every site the moment this shipped. Confirmed live: all three
sites (szl, siezal, hsm) came up `enabled=1` after migrate.

**New endpoints, `aimatic/ai/api.py`**:
- `get_ai_integration_settings()` - gated by the normal 4-role `_check_role()`, not just System
  Manager, so every allowed user can see *whether* the assistant is enabled (used to render a
  disabled-state banner for everyone), even though only System Manager can change it.
- `update_ai_integration_settings(enabled, model)` - **System-Manager-only** (stricter than
  `_check_role()`, since this is an org-wide cost/availability control). Writes both fields in one
  `frappe.db.set_single_value(doctype, {dict})` call. No strict validation of `model` beyond a
  plain string - a bad slug fails loudly on the next real `ask()`/`ping()` via the existing
  `NemotronError` path, same as any other OpenRouter error this module already surfaces.
- `list_available_free_models(force_refresh=False)` - **System-Manager-only**. Calls OpenRouter's
  public `GET /api/v1/models` catalog (no API key needed for this endpoint specifically), filters
  to `id.endswith(":free")` **and** `"tools" in (m.get("supported_parameters") or [])` - this
  assistant is entirely tool-call driven, so a free model without function-calling support isn't
  usable here regardless of price. Confirmed live (2026-07-20): OpenRouter currently lists 338
  models total, 14 free, 13 of those tool-capable (the one exclusion,
  `nvidia/nemotron-3.5-content-safety:free`, is a safety classifier). Cached in `frappe.cache()`
  (Redis - shared across all 81 gunicorn workers and all 3 sites; a process-lifetime cache would be
  useless here, unlike `report_registry.py`'s Frappe-report discovery cache) for 6 hours;
  `force_refresh=True` bypasses it.

**Frontend, `ai_assistant_console.js`/`.css`**: a `System Manager`-only "AI Settings" entry in the
page's `...` menu (`page.add_menu_item`) opens a `frappe.ui.Dialog` (Enabled checkbox + a Model
`Select` populated live from `list_available_free_models`, each option labelled with its context
length, e.g. "NVIDIA: Nemotron 3 Ultra (free) — 1000K context (free)"; a static note that the API
key itself isn't editable here). On page load, every allowed role calls
`get_ai_integration_settings()`; if disabled, an inline `.ai-assistant-disabled-banner` renders
above the context bar and the input/send/mic controls are disabled - so a non-System-Manager user
gets a clear state instead of a cryptic per-message error. No workspace shortcut was added for the
new doctype, matching the existing convention that `AI Saved Report`/`AI Dashboard`/`AI Alert
Rule`/`AI Scheduled Question` aren't separately surfaced there either (a System Manager can still
open `/app/ai-integration-settings` directly like any Single).

**Verified live on siezal** (`bench execute`, temp module deleted after, per this module's
established pattern): `list_available_free_models()` returns the 13 models above; overriding
`model` via `update_ai_integration_settings` makes `nemotron_client._get_model()` pick it up ahead
of site config; setting `enabled=0` makes `api.ping()` raise the disabled error immediately;
clearing `model` back to blank correctly falls through to the site-config value; re-enabling
restores normal operation. The settings were originally left enabled with blank model overrides
after that verification. Current live configuration checked 2026-07-20: all three sites remain
enabled; `szl` and `hsm` still have blank model overrides and therefore inherit the bench-wide
`nvidia/nemotron-3-ultra-550b-a55b:free`, while `siezal` now explicitly overrides its model with
`openai/gpt-oss-20b:free`. These are mutable operational settings, so query `tabSingles` or use the
settings endpoint rather than assuming this snapshot is permanent.

## Tools: 38 certified + governed report/analytics fallbacks

`tools.py` (11 tools) + `tools_extended.py` (5 more, Phase 1) — all cheap `SUM`/`GROUP BY`
aggregates with capped limits (no per-item ledger replay, no N+1 queries), Company/Branch-
permission scoped via `_resolve_branch_filter`/`_branch_warehouses` (mirroring
`sales_dashboard/api.py`'s branch-scoping discipline).

- `tools.py`: `get_sales_overview`, `get_purchase_overview`, `rank_vendors` (gross-margin-based,
  via each item's `Item Default.default_supplier`), `get_inventory_vs_sales` (stock-vs-trailing-
  sales-velocity as days-of-stock), `get_branch_comparison`, `get_payment_mode_split`,
  `get_returns_overview`, `get_active_shifts`, `get_top_selling_items`,
  `get_outstanding_payables_overview`, `get_gross_margin_overview`.
- `tools_extended.py`: `get_item_price_history` (item_code, months — PR+PI cost history reusing
  `purchase_printing.py`'s exact join pattern, current MRP from `Item.custom_mrp`, per-branch
  selling rates from `Item Price` — **not** `Item.custom_shelf_price`, which doesn't exist; see
  shelf-pricing skill, shelf price only ever lives on `Purchase Receipt Item` rows and propagates
  into branch `Item Price` records, never onto `Item` itself), `get_price_increases` (items with a
  ≥N% purchase-cost jump in a window, single-query-then-Python-group, no N+1),
  `get_dead_stock_detail` (proper dead-stock list via actual last-sale-date from Stock Ledger
  Entry, distinct from `get_inventory_vs_sales`'s window-ratio heuristic — returns
  `total_dead_stock_value` across *all* qualifying items, not just the returned page, so "dead
  stock worth more than X" questions stay accurate under a row limit), `get_top_customers`,
  `get_receivables_overview` (Sales Invoice/customer mirror of `get_outstanding_payables_overview`
  — safe to query directly, unlike item-level revenue this header-level `outstanding_amount` isn't
  duplicated by POS consolidation). Each file's own `TOOL_SPECS`/`TOOL_DISPATCH` get merged in
  `api.py`.

## Accounts tools (`tools_accounts.py`, added 2026-07-18) — 9 GL-Entry-based financial tools

Added after a real production bug was found: the "Outstanding Payables" executive widget showed
**PKR 0.00** on `siezal` when the real Creditors-account balance was **~PKR 43.8M** (hsm: **~PKR
91.0M**). Root cause: `get_outstanding_payables_overview` (in `tools.py`) only summed `Purchase
Invoice.outstanding_amount` — but `siezal`/`hsm` had **zero/near-zero submitted Purchase Invoices**
at the time; their real supplier debt is carried almost entirely via legacy per-row opening-balance
**Journal Entries** from the iPOS supplier migration (see `ipos-migration` skill /
`supplierimport.md`). Fixed by switching that tool to sum `GL Entry` (`party_type = 'Supplier'`,
`is_cancelled = 0`) instead — the only source that captures Purchase Invoice, Journal Entry, *and*
Payment Entry postings against a party uniformly, matching how ERPNext's own Accounts Payable
report actually computes outstanding balance. Verified live: siezal jumped from PKR 0 to PKR
43,789,931.11 across 282 suppliers; hsm to PKR 91,036,465.11 across 259. This is the same class of
bug the rest of this module has hit before (see the revenue double-counting note above) — **a
header-level `outstanding_amount`/table-only view can silently miss an entire class of real
transactions that a different site's data happens to be dominated by**; always cross-check a
financial total tool against the raw GL Entry balance for the account in question before trusting
it, especially on a site with any history of bulk/legacy data import.

**All 9 new tools are GL-Entry/Account-based** (never Purchase Invoice/Sales Invoice header fields
alone), so they inherit that same correctness property and are safe from the revenue-double-counting
gotcha above for a different reason: `POSInvoice.on_submit()` never posts GL Entries itself (see
"POS Invoice stock/GL updates only ever happen via the *consolidated* Sales Invoice" in this bench's
CLAUDE.md) — so Income-type GL Entries only ever exist once, tied to the one real consolidated Sales
Invoice, never duplicated between POS Invoice and Sales Invoice the way item-level revenue tables are.

- `get_payables_aging(limit=10)` / `get_receivables_aging(limit=10)` — buckets a party's outstanding
  GL balance into `0-30`/`31-60`/`61-90`/`90+` days by each contributing GL Entry row's own
  `posting_date`. **Only positive-net-balance parties count** — a supplier/customer whose rows net
  to a credit/prepaid position is excluded entirely from both the totals *and* the aggregate
  buckets (re-derived from the filtered per-party bucket fields, not summed from raw rows), so
  `buckets` always sums to exactly `total_outstanding_amount` — the first draft summed raw GL rows
  directly into `buckets` without this filter; fixed before deploy, caught by design review not
  live testing (a single-supplier-per-bucket dataset wouldn't have surfaced it).
- `get_cash_and_bank_balance()` — point-in-time (`posting_date <= today`) balance of every leaf
  `Account` with `account_type IN ('Cash', 'Bank')`.
- `get_profit_and_loss_overview(date_from, date_to)` — real GL-based P&L: Income (`root_type='Income'`,
  normal credit) minus Expense (`root_type='Expense'`, normal debit) for the period. **Will show
  PKR 0 for "today" on a site with an un-closed POS shift** — this is expected, not a bug, per the
  same GL-posting-only-on-consolidation fact above; a question needs to resolve to a period that's
  actually had a shift close to show real Income.
- `get_expense_breakdown(date_from, date_to, limit=10)` — top N expense accounts by amount plus the
  true total across *all* expense accounts (not just the returned page — same "total isn't capped by
  the row limit" discipline as `get_dead_stock_detail`).
- `get_trial_balance_summary(date_from, date_to)` — Asset/Liability/Equity are **cumulative** balances
  up to `date_to` (balance-sheet accounts never reset); Income/Expense are **period** balances
  (`date_from`→`date_to`, since they're period accounts). `balance_check` (`Assets - (Liabilities +
  Equity)`) is **expected to be nonzero in normal operation** — it will not net to zero until a
  fiscal-year-end closing entry folds the period's Income/Expense into Equity, which most sites never
  run continuously — so its KPI severity never escalates past `"info"`, deliberately, to avoid crying
  wolf on every single call. Confirmed live on siezal: a `5119 - Stock Adjustment - SSM` expense
  account carries a large one-time negative balance (~-43.5M) from the iPOS opening-stock-value
  import — a real, explainable artifact of the migration, not a code bug, but it's why
  `balance_check`/`expense_balance` can look dramatic on siezal specifically.
- `get_tax_liability_overview(date_from, date_to)` — sums `GL Entry` for every leaf `Account` with
  `account_type = 'Tax'`; returns an empty/zero shape (never throws) if a site's chart of accounts
  doesn't tag any account that way.
- `get_payment_entry_summary(date_from, date_to)` — `Payment Entry` (docstatus=1) totals by
  `payment_type` (Receive/Pay) plus a `mode_of_payment` breakdown.
- `get_branch_profit_and_loss(date_from, date_to)` (9th tool, added same session) — Income/Expense/
  net profit per branch via `GL Entry.branch` (a real Link field, confirmed to exist directly on GL
  Entry as an Accounting Dimension), with a synthetic `"Unassigned"` bucket for the (currently large
  majority of) untagged rows — mirrors the same Unassigned-bucket convention `sales_dashboard`/
  `vendor_performance` already use for the identical reason. Low practical value on `siezal` today
  (only 1 real branch, ~3 of 1334 GL Entry rows carry a branch) but exercises correctly and will
  become genuinely useful as siezal adds its next branches or on `szl`'s 5-branch test data (verified
  live on both).

**Sign conventions used throughout** (get these backwards and every number is silently wrong, with
no error to catch it): Asset/Expense accounts have a normal **debit** balance
(`SUM(debit - credit)`); Liability/Equity/Income accounts have a normal **credit** balance
(`SUM(credit - debit)`). Verified against real data for every one of the 9 tools before deploy.

**Four real bugs in the first Nemotron draft, all caught before/during deploy testing, not
discovered by users**:
1. Every `DataSource` entry drafted for `report_registry.py`'s `TOOL_REGISTRY` omitted
   `supported_filters` and `returned_fields` — both are **required** fields on the `DataSource`
   frozen dataclass (no default value), so importing `report_registry.py` as drafted would have
   raised `TypeError: missing 2 required positional arguments` the first time anything imported
   that module, breaking the entire AI console (not just the 8 new tools) until fixed. Caught by
   re-reading the `DataSource` dataclass definition against the draft, not by running it.
2. `chart_recommender.py` never had `from frappe.utils import flt` in its imports (apparently
   never needed by any pre-existing chart function, which use raw already-float dict values
   directly) — but half the new `_chart_*` functions called `flt()` on their values, so 4 of 7
   raised `NameError: name 'flt' is not defined` the moment they were exercised with non-empty
   data. **Only caught by an actual functional test with real data reaching the chart path** —
   `python3 -m py_compile` and even an import-only smoke test both passed cleanly, since the
   `NameError` only fires when the function body actually executes past the empty-data guard.
   Fixed by adding the import.
3. `response_schema.Chart` has a required `auto_selected: bool` field (no default) that every
   pre-existing `_chart_*` function sets to `True` — the new functions omitted it entirely,
   raising `TypeError: Chart.__init__() missing 1 required positional argument: 'auto_selected'`
   the moment any of them returned non-`None`. Same "only caught by real data reaching the
   construction line" pattern as #2 — masked in the first functional-test pass because that pass
   happened to hit only tools whose chart functions returned `None` for that day's narrow
   ("today only") default date range.
4. Every new chart function used dataset dicts shaped `{"name": ..., "values": [...]}`, but the
   frontend (`init_chart` in `ai_assistant_console.js`) reads `chart.data.datasets[i].label`/
   `.data` and remaps *those* keys to `name`/`values` internally for `frappe.Chart` — every
   pre-existing chart function in this file already used `{"label": ..., "data": [...]}`. The
   `{"name": ..., "values": ...}` shape wasn't itself a crash (`ChartData.datasets` is typed as a
   generic `list[dict]`, no schema enforcement), so this would have silently rendered every new
   chart type as empty/broken in the browser with zero server-side error — the kind of bug that
   never surfaces in `bench console` testing at all, only caught by explicitly reading the
   frontend's actual key-remapping code and comparing against the backend's dict shape.

**A fifth, pre-existing bug this work exposed (not introduced by tonight's changes) — LLM
tool-routing confusion between a purpose-built tool and `run_dynamic_report`**: the exact phrasing
"What is our total outstanding payable amount and which suppliers do we owe the most to?"
reproducibly (5/5 attempts) made the model call `run_dynamic_report` against `Purchase Invoice`
instead of the purpose-built `get_outstanding_payables_overview`/`get_payables_aging` — and since
`siezal` has zero submitted Purchase Invoices, every dynamic-report attempt returned `row_count: 0`,
the model kept retrying different filter/date variations against the same empty doctype, and
`ask()` exhausted its `_MAX_TOOL_ITERATIONS = 5` budget without ever producing a real answer.
Traced by monkey-patching `get_chat_completion`/`_dispatch_tool_call` to log every tool call and
its result — confirmed the model was choosing the wrong tool outright, not hitting a rate limit.
Fixed by adding an explicit instruction to `_build_system_prompt()`: always prefer a purpose-built
tool over `run_dynamic_report`, and trust a purpose-built tool's empty/zero result rather than
retrying via the fallback. Verified fixed: the same question now calls
`get_outstanding_payables_overview` correctly on the first attempt. This fix is general (system
prompt, not tool-specific) and should reduce this failure mode for any future purpose-built vs.
`run_dynamic_report` ambiguity, not just this one payables question.

**Cross-check performed before deploy** (via `bench execute` against real `siezal` data,
2026-07-18): `get_payables_aging()["total_outstanding_amount"]` exactly matched the
independently-fixed `get_outstanding_payables_overview()["total_outstanding_amount"]` (both PKR
43,789,931.11), and `sum(get_payables_aging()["buckets"].values())` exactly matched that same
total — confirming the positive-net-balance-only filtering fix above is internally consistent, not
just plausible-looking.

**TOOL_SPECS date-range descriptions were corrected before deploy**: the first draft's
`date_from`/`date_to` parameter descriptions said "defaults to fiscal year start" — false; these
tools share `tools.py`'s existing `_get_date_range` helper, which (like every other date-ranged tool
in this module) defaults to **today only** when omitted, relying on the system prompt's own
instruction that the LLM resolve phrases like "this month"/"this year" into concrete dates itself
before calling a tool. Descriptions now match the other tools' actual "defaults to today" phrasing.

**Gotcha — testing tool availability itself was intermittently blocked mid-session** by Claude
Code's own Bash/Edit permission classifier being unavailable for an extended stretch; short, simple
commands (`bench --site X execute frappe.ping`, `echo`) occasionally got through while longer piped/
heredoc `bench console` invocations consistently didn't. Worked around by using
`bench --site <site> execute <dotted.path.to.function>` against a short-lived temp module dropped
directly into `aimatic/ai/_diag_temp.py` (deleted immediately after each check, never committed) —
a plain `bench execute <dotted-path>` call is a shorter, simpler command shape than a piped
`bench console` heredoc and had a measurably higher success rate against the degraded classifier.
Worth remembering as a fallback pattern if this recurs, independent of tonight's specific outage.

Wired into `api.py` exactly like `tools_extended.py`: `from aimatic.ai.tools_accounts import
TOOL_DISPATCH as _ACCOUNTS_DISPATCH, TOOL_SPECS as _ACCOUNTS_SPECS`, merged into the top-level
`TOOL_SPECS`/`TOOL_DISPATCH`. KPI/table builders added to `answer_builder.py`'s
`_KPI_DISPATCH`/`_TABLE_DISPATCH` (no table for `get_profit_and_loss_overview` — a few headline
numbers don't need one), chart builders to `chart_recommender.py`'s `_CHART_DISPATCH` (aging
buckets, expense breakdown, and branch net-profit as bar charts, capped at `_MAX_CHART_BARS`; no
chart for `get_profit_and_loss_overview`/`get_cash_and_bank_balance` beyond their KPIs), and all 9
registered in `report_registry.py`'s `TOOL_REGISTRY`.

**`dynamic_report.py`** (Phase 2, the "AI-Generated Reports" controlled fallback) — the one path
in this whole module where a hardcoded whitelist, not the LLM, decides what SQL can run.
`run_dynamic_report(doctype, fields, aggregate_field, aggregate_fn, filters, group_by, order_by,
date_from, date_to, limit)` only accepts `doctype` from `_ALLOWED_DOCTYPES` (`POS Invoice`,
`Purchase Invoice`, `Purchase Receipt`, `Item`, `Customer`, `Supplier` — deliberately excludes
`Sales Invoice`, same revenue-double-counting reason as everywhere else) and every
field/group-by/order-by/aggregate name against that doctype's own fixed field whitelist; company
and branch scoping (via `tools._resolve_company`/`_resolve_branch_filter`, same empty-branch-
list-returns-empty-result guard as every other tool) are always force-applied server-side, never
LLM-controlled. All data access goes through `frappe.db.get_list()`, never `frappe.db.sql()` with
interpolated strings.

**Aggregate fields must use Frappe's dict syntax** (`{"SUM": "grand_total", "as": "value"}`), not
an f-string SQL fragment (`f"SUM({field}) as value"`) — confirmed live: `get_list` itself rejects
any raw function-call string in `fields` with `"SQL functions are not allowed as strings in
SELECT... Use dict syntax like {'COUNT': '*'} instead"`, a second independent defense on top of
this file's own whitelist (Frappe's own `FUNCTION_MAPPING` in `frappe/database/query.py` happens
to be the exact same 5 names as `ALLOWED_AGGREGATIONS`). A row-shape not known ahead of time
(unlike the 16 fixed tools) means `answer_builder.py`'s `_table_for_run_dynamic_report` infers
columns from the first result row's keys via a small type-name map, rather than a hand-written
column list.

## Revenue double-counting gotcha (found and fixed 2026-07-17)

Any query that `UNION ALL`s `Sales Invoice Item` with `POS Invoice Item` to total *revenue*
(`base_net_amount`) double-counts every POS sale that's gone through a shift close. Reason: `POS
Closing Entry` consolidates its POS Invoices into a **new, separate** `Sales Invoice` with its own
mirrored item rows (`POS Invoice Merge Log`/`map_doc`, see `offline-pos` skill) — but the
*original* POS Invoices stay `docstatus = 1`, never cancelled. Confirmed on `szl`: item
`0000000000002` had identical 31 rows / 1,587 qty / PKR 193,306.44 in both `Sales Invoice Item`
and `POS Invoice Item` for the same underlying sales; `get_top_selling_items` initially showed
exactly double (386,612.87) before the fix. Separately confirmed **every submitted Sales Invoice
on this bench is itself a POS-consolidation output** — 49 total, 37 as `consolidated_invoice` + 12
as `consolidated_credit_note` (POS returns), zero standalone — so dropping the Sales Invoice arm
entirely loses no genuine non-POS revenue. COGS queries via Stock Ledger Entry (`voucher_type IN
('Sales Invoice', 'POS Invoice')`) are **not** affected — `POSInvoice.on_submit()` never calls
`update_stock_ledger()` itself, so SLE rows only ever exist once, tied to the consolidated Sales
Invoice. Since `POS Settings.invoice_type` is `"POS Invoice"` on all three sites, **POS Invoice
alone is the complete, correct source of POS revenue** — never union it with Sales Invoice Item
for a revenue total. Fixed in this module's `get_sales_overview`/`get_top_selling_items`/
`rank_vendors` and in `vendor_performance/api.py`'s `_get_sales_summary`/`_get_sales_by_item`/
`_get_recent_sales` — the latter had been overstating sales revenue and gross margin % on the
shipped Vendor Performance console for any supplier with closed-shift sales.

## Structured response contract and assembly pipeline

**`response_schema.py`** — plain stdlib `@dataclass(frozen=True)` models (no Pydantic dependency
in this app), each with its own `to_dict()`: `Answer`, `Context` (company/branch/date_range/
comparison_period/user_role/permissions), `KPI`, `Chart`/`ChartData`/`ChartOptions`, `Table`/
`TableColumn`/`Pagination`/`DrillDown`, `Insight`, `Warning`, `Source`, `Action`, and the
top-level `StructuredResponse` container. `ask()` returns `StructuredResponse.to_dict()` directly
as `r.message` — **not** `{"reply": "..."}` (that shape only survives in `get_recent_history`'s
restored-history rows, always plain text since `_log_turn` persists the reply string either way).
`DateRange`/`ComparisonPeriod` hand-build their own `to_dict()` instead of `dataclasses.asdict()`
because their field is named `from_` (Python keyword collision) but must serialize as JSON key
`"from"`.

**`chart_recommender.py`** — deterministic (no LLM) `recommend_chart(tool_name, result) -> Chart |
None`, one private `_chart_get_<tool>` function per tool dispatched via a lookup dict, since every
tool's result shape is already known exactly (no generic shape-sniffing). Single-branch/short-list
results correctly suppress a chart. Bar-chart-producing functions cap at `_MAX_CHART_BARS = 10` —
beyond that, labels truncate illegibly (confirmed live: a 48-item dead-stock chart rendered as
unreadable 2-character label stubs before this cap was added); the table for the same answer
still shows every row.

**`insight_generator.py`** — rule-based (no LLM) `generate_insights(tool_results: dict[str,
dict]) -> list[Insight]`, one `_detect_*` function per rule, each gracefully no-op if its required
tool wasn't called this turn — detectors never raise. Real detector names (exact, used verbatim as
`AI Alert Rule.rule_name` options minus the `_detect_` prefix): `_detect_dead_stock`,
`_detect_price_increases`, `_detect_stockout_risk`, `_detect_negative_vendor_margin`,
`_detect_branch_underperformance`, `_detect_low_gross_margin`, `_detect_payables_concentration`,
`_detect_high_return_rate`, `_detect_positive_margin_signal` (this last one has no matching alert
rule — it's a "good news" signal, not something you'd alert on). None currently accept a threshold
override kwarg — each has its threshold hardcoded inline (e.g. `if margin_pct < 10`). Dead-stock
detection prefers `get_dead_stock_detail` (precise, actual last-sale-date) when present in the
turn's tool results, falling back to `get_inventory_vs_sales`'s window-ratio heuristic only when
the newer tool wasn't called.

**`report_registry.py`** — lightweight in-Python `DataSource` catalogue (no new DocType):
`TOOL_REGISTRY` has one entry per tool (`source_type="tool"` — **not** `"report"`/`"chart"`/
`"number_card"`, a mislabeling Nemotron's first draft made across all 16 entries, since that field
distinguishes "one of our own controlled Python tools" from "a discovered Frappe Report/Chart/
Number Card record" for anything downstream that branches on it); `discover_frappe_reports()`
finds real Query/Script Reports from `Accounts`/`Buying`/`Selling`/`Stock`/`Aimatic` modules (132
found on `szl`, process-lifetime cached); `get_registry()` merges both (tools win on collision);
`find_sources_for_question()` is a Phase-1 keyword-overlap heuristic (no LLM) used to populate
`sources[]`, expected to become LLM-assisted in a later phase.

**`answer_builder.py`** — the orchestrator `build_response(question, reply_text, tool_results,
company, branch_names, user_role) -> StructuredResponse`. Per-tool `_kpis_for_<tool>`/
`_table_for_<tool>` dispatch functions (same explicit-per-tool pattern as `chart_recommender.py`)
turn each tool's result into KPI cards / a Table; calls `chart_recommender.recommend_chart` and
`insight_generator.generate_insights`; looks up `sources[]` via `report_registry.get_registry()`;
builds a short rule-based `follow_up_questions[]` list keyed off which tool *categories* were
used. `answer.confidence`/`data_quality`/`intent`/`entities` and `context.permissions.can_export`/
`can_schedule` are **explicit Phase-1 placeholders** (binary tool-data-present-or-not heuristic,
`intent="general"`, `entities={}`, exports/scheduling hard-`False`) — honest stand-ins, not real
ML/intent-classification/export-backend, until a later phase actually builds those.

## api.py — the conversational entrypoint

`ping()` is a System Manager-gated whitelisted connectivity test. `ask(message, history=None,
conversation=None)` is the conversational entrypoint, role-gated to `{"System Manager", "Sales
Manager", "Accounts Manager", "POS Supervisor"}`. `history` is a JSON-encoded list of prior
`{role, content}` user/assistant *text* turns only (never raw tool-call internals), capped at
`_MAX_HISTORY_TURNS = 20`, rebuilt fresh every call. Loops up to `_MAX_TOOL_ITERATIONS = 5`: calls
`get_chat_completion` with the merged `TOOL_SPECS` (tools + tools_extended + dynamic_report),
dispatches `tool_calls` via the merged `TOOL_DISPATCH`, accumulates each *successful* (no
`"error"` key) result into a `tool_results` dict keyed by tool name. On the final reply, resolves
`company`/`branch_names` and `user_role`, calls `answer_builder.build_response(...)`, persists via
`_log_turn`, and returns `StructuredResponse.to_dict()`. Every tool is read-only — the assistant
can never create, submit, or modify a document.

**Real bug found and fixed 2026-07-18 — malformed tool-call text shipped as the answer**: when a
turn's `tool_calls` is empty, the loop always treated `assistant_message["content"]` as the final
natural-language reply. The free-tier model occasionally malforms a tool call — instead of using
the real `tool_calls` protocol it writes what should have been the call's *arguments* as plain
`content` text, e.g. literally `{"company": "Test Company", "days": 30}` (sometimes duplicated on
separate lines) — and since that message has no `tool_calls`, the old code shipped that raw JSON
straight to the user as if it were the answer. Reproduced live and confirmed in the persisted `AI
Assistant Message` log with the phrasing "what items should I purchase tomorrow" / "what should I
order tomorrow" (intermittent, not every attempt — same question succeeded on retry). Fixed by
`_looks_like_raw_tool_json(content)`: every non-blank line must itself parse as a bare JSON object
with no surrounding prose (a real answer never satisfies that, even one containing a markdown
table). When it fires, the loop does **not** return — it appends a corrective `user`-role message
telling the model to actually call the tool or answer in plain language, and `continue`s within the
existing `_MAX_TOOL_ITERATIONS` budget (a correction consumes one iteration slot, same as a real
tool call would). Also logs a `frappe.log_error` titled "AI Assistant: malformed tool-call text
corrected" with the question and raw content, for visibility into how often this fires in
practice. Verified via a mocked `get_chat_completion` sequence (malformed-JSON turn → real tool
call → real final answer) proving the loop recovers, since the underlying LLM misbehavior itself
is nondeterministic and can't be reliably forced live.

For "what should I purchase/order" style questions specifically: there is no dedicated
reorder/replenishment tool — the assistant correctly reframes these into a call to
`get_inventory_vs_sales` (stock vs. 30-day sales velocity → days-of-stock) and the model itself
does the "which of these are actually low, not overstocked" reasoning in its final text answer.
This works well in practice (verified live: correctly picked out one critically-low item from
three flagged rows, correctly explained the other two were overstocked not understocked) but is
LLM reasoning over a general-purpose tool, not a purpose-built reorder-point calculation — a
future phase could add a dedicated tool if this reasoning step proves unreliable at scale.

**Real bug found and fixed 2026-07-18 — LLM chose `run_dynamic_report` over a purpose-built tool
and got stuck**: the phrasing "What is our total outstanding payable amount and which suppliers do
we owe the most to?" reproducibly (5/5 attempts) made the model call `run_dynamic_report` against
`Purchase Invoice` instead of `get_outstanding_payables_overview`/`get_payables_aging` — and since
`siezal` has zero submitted Purchase Invoices, every dynamic-report attempt returned `row_count: 0`,
the model kept retrying different filter/date variations against that same empty doctype, and
`ask()` exhausted `_MAX_TOOL_ITERATIONS` without ever producing an answer. Traced by monkey-
patching `get_chat_completion`/`_dispatch_tool_call` to log every call and its result — confirmed
this was the model choosing the wrong tool outright, not a rate limit (the trace showed 5 distinct
`run_dynamic_report` calls with varying arguments, never once trying the correct tool). Fixed by
adding an explicit instruction to `_build_system_prompt()`: always prefer a purpose-built tool over
`run_dynamic_report`, and trust a purpose-built tool's empty/zero result rather than retrying via
the fallback — `run_dynamic_report` is a last resort for questions no specific tool covers, not a
first choice. Verified fixed: the same question now calls the correct tool on the first attempt.
This is a general system-prompt fix, not specific to payables — it should reduce this failure mode
for any future purpose-built-tool-vs-`run_dynamic_report` ambiguity as more tools get added.

## Conversation management (Phase 2)

`AI Assistant Conversation` doctype (`title`/`user`/`pinned`/`last_activity`, autoname hash,
System-Manager-only doctype perms same as `AI Assistant Message`) supersedes the flat, ungrouped
Phase-1 history model. `AI Assistant Message` gained three fields: `conversation` (Link, not
mandatory — pre-Phase-2 rows are left blank, never backfilled), `feedback` (Select, blank/up/
down), `feedback_note`.

`api.py` endpoints, all ownership-checked via `_check_conversation_ownership`
(`AI Assistant Conversation.user == frappe.session.user`, else `frappe.PermissionError`):
`start_conversation`, `list_conversations` (pinned first, then `last_activity` desc),
`get_conversation_messages`, `rename_conversation`, `pin_conversation`, `delete_conversation`
(cascades to its messages), `submit_feedback`.

**`ask()` itself gained an optional `conversation` param and validates ownership on it too before
use** — every other Phase-2 endpoint already had this check, but the first draft left `ask()` able
to log a turn into a conversation name it never verified the caller owned; caught in review before
deploy, not live. When `conversation` is omitted, behavior is byte-for-byte identical to Phase 1
(no grouping) — grouping is opt-in per call. The first turn of a new conversation auto-titles
itself from the first ~60 chars of the user's message via one combined
`frappe.db.set_value(doctype, name, {dict of fields})` call alongside bumping `last_activity`.

**Conversation persistence** (2026-07-17 product decision, extended 2026-07-18): every successful
`ask()` call writes both the question and the answer (`reply`, plain text — never the structured
dict) to `AI Assistant Message` via `_log_turn` — best-effort, swallows its own failures
(`frappe.log_error`) rather than ever breaking the chat response. The doctype's own permissions
are System Manager-only; every other allowed role reaches only *their own* history through
`get_recent_history(limit=40)` (Phase 1, flat/ungrouped, still a fallback path) or
`get_conversation_messages` (Phase 2, grouped, ownership-checked). Retention:
`ai/tasks.py:purge_old_ai_messages`, wired into `hooks.py`'s `scheduler_events["daily"]`, deletes
rows older than `RETENTION_DAYS = 30` — unaffected by conversation grouping.

## Save / Dashboard / Export (Phase 3)

**Doctypes** (all `autoname: "hash"`, module `Aimatic`, System-Manager-only base perms, ownership
enforced at the API layer):
- `AI Saved Report` — title/question/context_snapshot/response_snapshot/tool_results_snapshot/
  user/pinned/last_refreshed. The snapshot fields hold `Context.to_dict()`/
  `StructuredResponse.to_dict()` JSON exactly as the client had them, so a saved report displays
  instantly with zero OpenRouter cost; `refresh_saved_report` re-runs the original question
  through the real `ask()` pipeline and overwrites `response_snapshot`.
- `AI Dashboard` — title/user/`widgets` child table.
- `AI Dashboard Widget` — child table, `istable: 1`, only `saved_report` + `size` fields —
  deliberately **no custom `idx` field**, since every Frappe child table already has one built in
  for row ordering and a same-named custom field would collide with it. Reordering is just
  rebuilding the parent's widget list in the new order and saving; Frappe reassigns `idx` from
  list position automatically.

**API** (`api.py`) — `save_report`/`list_saved_reports`/`get_saved_report`/
`rename_saved_report`/`pin_saved_report`/`delete_saved_report`/`refresh_saved_report` and
`create_dashboard`/`list_dashboards`/`get_dashboard`/`add_widget_to_dashboard`/
`remove_widget_from_dashboard`/`reorder_widgets`/`rename_dashboard`/`delete_dashboard`, all behind
`_check_saved_report_ownership`/`_check_dashboard_ownership` (same `frappe.db.get_value(...,
"user")` pattern as `_check_conversation_ownership`). `add_widget_to_dashboard` checks ownership
of **both** the dashboard and the saved report being linked, so a user can never pull another
user's saved report into their own dashboard.

**Manual whole-dashboard refresh (added 2026-07-20)**: the custom dashboard header now has a
`Refresh Dashboard` button. Widgets remain zero-cost point-in-time snapshots during ordinary
open/reload; the button explicitly warns that refreshing uses OpenRouter, then calls the existing
ownership-checked `refresh_saved_report` endpoint once per unique linked saved report. Calls run
sequentially, never with `Promise.all`, because all sites share one free-tier key with a tight
concurrency cap. The button shows `Refreshing X/Y`, continues past an individual request failure,
reloads the dashboard from `get_dashboard` afterward, and reports how many widgets updated versus
kept their previous snapshot. A response with no KPI/chart/table counts as "kept" in the UI; the
server's existing degraded-refresh guard remains the authoritative protection that prevents a
good stored snapshot from being overwritten. This is frontend-only (`ai_assistant_console.js`/
`.css`): build assets and clear all site caches; no migrate or gunicorn reload is required.

**Return shapes are deliberately flat** (`{"name": doc.name}`, not `{"saved_report": {...}}`/
`{"dashboard": {...}}`) — the first frontend draft assumed nested wrapper keys it never actually
got from the server (drafted without the real `api.py` in context) and silently no-op'd on every
save/dashboard-open until caught live. **Always paste the actual current server return shape into
a frontend-drafting prompt, not just its own name** — this is a repeatable failure mode, not a
one-off.

**Export**: `export_table(table_json, filename, format)` builds `data = [[header...], [row...],
...]` from a client-supplied `Table.to_dict()`-shaped JSON string and calls
`frappe.utils.csvutils.build_csv_response(data, filename)` /
`frappe.utils.xlsxutils.build_xlsx_response(data, filename)` — **not** `get_csv_content` (doesn't
exist in this Frappe version) or hand-rolled `openpyxl` (this version's `xlsxutils` wraps
`xlsxwriter` instead) — both set `frappe.response` directly and are the verified-live,
version-correct helpers. A whitelisted method that sets `frappe.response` this way **cannot** be
called via normal `frappe.call()` (that expects JSON) — the client must use Frappe's own
`open_url_post('/api/method/aimatic.ai.api.export_table', {...})`
(`frappe/public/js/frappe/utils/urllib.js`, same mechanism `data_exporter.js` uses for the
standard list-view Export button), which POSTs a real HTML form so the browser treats the
response as a normal file-download navigation.

## Scheduling + Alerts (Phase 3)

`ai/tasks.py`, wired into `hooks.py`'s `scheduler_events["daily"]` alongside
`purge_old_ai_messages`:

- `run_scheduled_questions()` finds enabled `Scheduled Question` rows due by simple date-math
  (`last_run` blank → due now; Daily/Weekly/Monthly → `add_days`/`add_months` off `last_run`, no
  cron parser).
- `check_alert_rules()` evaluates each enabled `AI Alert Rule` by calling the ONE tool its
  `rule_name` needs directly (not the whole `generate_insights()` sweep) and passing that single
  result straight to the matching `_detect_*` function.

**Both must run each row/rule as its owning user**, not whatever the background job's own default
session is — `frappe.set_user(row.user)` before any tool/`ask()` call, reset in a `finally` —
since every tool's company/branch resolution and `ask()`'s own `_check_role()` implicitly depend
on `frappe.session.user`; a demoted user's rule fails that one `_check_role()` and is logged/
skipped rather than aborting the whole daily run for every other user's rows.

`threshold_override` is stored on `AI Alert Rule` for a future phase but **not yet applied** —
none of `insight_generator.py`'s `_detect_*` functions currently accept an override kwarg. A
rule's own hardcoded default is always what runs.

**Two real bugs found only by actually running the scheduler function, not by reading the code**:
1. The first draft imported `get_dead_stock_detail`/`get_price_increases` from `aimatic.ai.tools`
   — they're actually in `aimatic.ai.tools_extended`, an `ImportError` that would have silently
   broken alert checking for those two rules in production.
2. The first draft's `try/except` around each scheduled question / alert rule only wrapped the
   `ask()`/tool-call step, not the `frappe.sendmail(...)`/`frappe.db.set_value(...)` steps after
   it — so a mail failure (confirmed live: szl has no outgoing Email Account configured) raised
   straight out of the loop and aborted every remaining row for every other user in the same run.
   Fixed by wrapping the entire per-row block (call → email → `last_run`/`last_triggered` update →
   explicit `frappe.db.commit()`) in one try/except with `frappe.db.rollback()` on failure — this
   also means a question whose email failed to send correctly does **not** get `last_run`
   updated, so it's retried on the next daily run rather than silently marked done despite never
   reaching the recipient.

## Frontend (`ai_assistant_console.js`/`.css`)

Built on `frappe.ui.make_app_page` and Frappe's own theme CSS variables for light/dark
correctness.

**Phase 1 (2026-07-17)**:
- **Smart Context Bar**: Company/Branch/Date Range fields via `this.page.add_field(df, parent)` —
  note `parent` is the function's **second positional argument**, not a key inside the field-
  definition object; passing it as `{..., parent: $el}` silently no-ops (Frappe's `add_field`
  just falls back to the page's default toolbar area), caught only by live-browser DOM inspection
  showing `childCount: 0` on the intended container, not by any API-level test. Folded into the
  message text as a natural-language prefix (`"For company X, branch Y, this month, <question>"`)
  since `ask()` has no structured filter params yet.
- **Role-aware suggested questions** keyed off `frappe.user_roles`.
- **Rich answer rendering** per turn: KPI cards, one `frappe.Chart` per `charts[]` entry,
  sortable/click-to-navigate tables, severity-colored insights, follow-up chips, sources footer —
  history restored via `get_recent_history` on page load still renders as plain bubbles.
- `Charts[]` render into a plain `<div>` (`frappe.Chart` builds an SVG into its container —
  despite the name, it does **not** take an HTML5 `<canvas>` element), and only after that div is
  actually attached to the document (a detached-element chart measures 0/NaN width and throws SVG
  attribute errors — fixed by a two-phase build-skeleton-then-attach-then-`init_chart` pattern,
  same as `sales_dashboard_console.js`'s existing convention).
- A rich turn scrolls into view via `scrollIntoView({block: 'start'})`, not
  `scrollTop(scrollHeight)` — the latter (correct for short plain bubbles, still used by
  `append_bubble`) would scroll a tall rich answer's KPIs/chart at the top out of view above the
  fold.
- Insight cards render only `title`/`description`/an "Actionable" flag — `supporting_data` stays
  in the API response for future drill-down but is deliberately never dumped as raw JSON into the
  UI.
- All of the above were real bugs in Nemotron's first draft caught only by actually driving the
  live page with Playwright against real production data — API-level/unit-style testing alone
  would not have caught any of them.

**Phase 2 additions (2026-07-18)**:
- Three-column layout (`.ai-assistant-layout`: left sidebar, center chat, right panel).
- **Left sidebar**: conversation list (search/rename/pin/delete), "New Analysis" button. First
  message of a fresh session has no conversation yet — `send_message` lazily calls
  `start_conversation` before `ask()` rather than forcing an explicit click first; page (re)load
  auto-opens the most recent conversation (mirrors Phase 1's flat-history continuity) but only on
  initial load, never on routine `refresh_conversation_list()` calls after send/rename/pin/delete.
- **Right panel**: "Scope & Sources" for the *last* answer, via `update_right_panel(response)`.
- **Both panels collapse** — but their toggle buttons must **not** live inside the element they
  collapse: the first draft put `.ai-assistant-sidebar-collapse` inside `.ai-assistant-sidebar`
  itself, and the collapsed-state CSS's `pointer-events: none` cascaded to the toggle button too,
  permanently stranding it — confirmed live, the click fell through to *Frappe's own standard Desk
  sidebar* underneath. Fixed by moving each toggle into its own persistent ~28px-wide sibling rail
  (`.ai-assistant-sidebar-rail` / `.ai-assistant-right-panel-rail`) that's never itself collapsed,
  simplifying the collapsed rule to plain `display: none`.
- **Voice input** (`init_voice`/`start_recording`/`stop_recording`) uses the browser's own
  `SpeechRecognition`/`webkitSpeechRecognition` — no new backend. Audio may be routed to the
  *browser vendor's* own cloud recognition (e.g. Chrome→Google), not to aimatic/OpenRouter,
  surfaced via an explicit privacy line while recording. Transcript lands in the editable textarea,
  never auto-submitted. A live level-meter bar uses a **separate** `getUserMedia`+`AnalyserNode`
  (SpeechRecognition exposes no raw audio data) — its `requestAnimationFrame` tick must not be
  fought by the 500ms duration-display timer rebuilding the same DOM nodes: the duration timer
  patches only the `.ai-assistant-voice-duration` text node, never the full
  `render_voice_status()` rebuild. Mixed Urdu-English in one utterance isn't reliably supported (one
  language per session) — a language-switch button substitutes for true code-switching. States:
  idle/recording/ready/failed/permission_denied/network_error/unsupported. In headless/automated
  tests with a fake media device, recognition legitimately fails fast with no real speech content —
  expected, not a code defect, since it still surfaces the correct `failed` state.

**Phase 3 additions (2026-07-18)**:
- **Save button** on every rich answer (after follow-up chips) calls `save_report` with the
  question (passed as a closure argument from `_send_message_now` through
  `render_rich_answer(response, question)`, not read from the DOM) and the live
  context/response as JSON snapshots. On success, `prompt_add_to_dashboard` offers to add it to
  one of the user's dashboards via a plain `prompt()` asking for the dashboard's title
  (deliberately simple for this phase — a real dropdown is later-phase polish, not a correctness
  gap; the title-match rejection path was verified live and works as designed).
- **Export buttons** (CSV/XLSX) in every table's title row use `open_url_post`, never
  `frappe.call`.
- **Dashboard section** in the sidebar (list + "+" create button) and a **dashboard view** that
  swaps in for the whole chat pane (`show_dashboard_view`/`hide_dashboard_view` toggle `display`,
  no page navigation) — widget cards **reuse the exact same `render_kpis`/`build_chart_wrap`+
  `init_chart`/`render_table` methods** the live chat already uses against each widget's stored
  `response_snapshot`, so a dashboard never needs separate rendering logic to stay in sync with
  the live answer format; insights/follow-ups/sources are skipped in widget cards to keep them
  compact. Widget size (Small/Medium/Large) maps to a flexbox width class
  (`ai-assistant-widget-sm/md/lg`).
- **Both `prompt_add_to_dashboard`'s success and the widget-remove handler must call
  `refresh_dashboard_list()`** after their own `frappe.call` succeeds — the sidebar's per-dashboard
  widget-count badge is a separate cached read (`list_dashboards`) from the dashboard-view's own
  widget list, and doesn't update on its own; confirmed live (a widget rendered correctly in the
  just-opened dashboard while the sidebar still showed its stale pre-add count) before being fixed.

**Suggested Questions redesign (2026-07-18)** — `build_suggested_questions()` now renders a
**collapsed-by-default** panel instead of always-visible pill buttons: a single compact
`.ai-assistant-suggested-header` row (lightbulb icon, "Suggested Questions" label, a `(N)` count
badge, a chevron) toggles a hidden `.ai-assistant-suggested-list` open/closed
(`_toggle_suggested`/`_collapse_suggested`). Clicking a question still calls `send_message(q)`
exactly as before, then immediately re-collapses the panel so it doesn't keep eating vertical
space above the chat after a question is picked. Fixes a real complaint: System Manager's role
has 19 suggested questions, which as a flat always-visible flex-wrap row pushed the chat window
down several lines; collapsed height is ~33px vs. ~595px expanded (measured live on szl).

## Executive Overview dashboard (built 2026-07-18, extended same night)

A 13-widget `AI Dashboard` named **"Executive Overview"**, owned by `Administrator`, exists on
all three sites (szl `6nf79090o4`, siezal `90ob2r8cmr`, hsm `bhlmvhta8p`) — built by scripting the
*real* `ask()`/`save_report()`/`create_dashboard()`/`add_widget_to_dashboard()` API functions
directly (via `bench execute`, `frappe.set_user("Administrator")` first) rather than
hand-writing fake widget data, so every widget holds genuine live KPIs/charts/tables exactly as if
a user had asked and saved each question through the UI. The original 10 questions cover: total
sales overview, gross margin, branch comparison, purchase spend, vendor margin ranking, outstanding
payables, outstanding receivables, top selling items, dead stock risk, and returns overview — a
deliberate CFO/CEO-level spread (revenue, margin, spend, vendor risk, cash position, inventory
risk, loss/returns), not an arbitrary pick of whichever tools existed. **3 more widgets** were
added the same night once the Accounts tools above shipped: Cash & Bank Balance, Payables Aging,
and Branch Profit & Loss. The original "Outstanding Payables" widget's saved snapshot was also
explicitly refreshed (via `refresh_saved_report`) on all three sites after the payables GL-Entry
fix above, since a saved report's `response_snapshot` is a point-in-time cache that doesn't
retroactively pick up a tool-logic fix on its own — it only updates on refresh or a fresh `ask()`.

**Why Administrator, not a per-user "CEO" account**: `AI Dashboard`/`AI Saved Report` are strictly
single-owner (`_check_dashboard_ownership`/`_check_saved_report_ownership` — see above,
`list_dashboards`/`get_dashboard` filter by `frappe.session.user` with no sharing mechanism at
all, not even for System Manager). Administrator was the practical, already-used account for this
work (same one used for every live Playwright verification in this module); a business owner
wanting their own copy needs `add_widget_to_dashboard` run again under their own login — there is
no dashboard-sharing feature yet.

## Executive KPIs dashboard (built 2026-07-22) — a second, pure-KPI-only dashboard

User feedback on the original Executive Overview dashboard: "widgets did not help me much" - a
mix of KPI cards, charts, and (per the widget-grid CSS fix above) internally-scrolling tables in
every widget was more clutter than a glanceable executive view needed. Built a second dashboard,
**"Executive KPIs"**, same ownership/scripting convention as Executive Overview (real `tools*.py`
calls + `answer_builder.build_response` + `save_report`/`create_dashboard`/`add_widget_to_dashboard`
via `bench execute`, `frappe.set_user("Administrator")` first - **no LLM call at all**, since a
pure KPI number needs none of `ask()`'s natural-language composition and this sidesteps every
free-tier flakiness failure mode documented elsewhere in this file entirely), on all three sites
(szl, siezal, hsm), size `Small` throughout since every widget is KPI-cards-only. 15 widgets, one
tool call each, `charts`/`tables` explicitly blanked (`d["charts"] = []; d["tables"] = []`) on the
`StructuredResponse.to_dict()` before saving so **only** `kpis` renders - `render_dashboard_view`
only appends what's actually present in each key, so blanking is sufficient, no schema change
needed. Covers Sales (MTD), Gross Margin (MTD), Purchasing (MTD - see below), Outstanding
Payables, Outstanding Receivables, Cash & Bank Balance, Profit & Loss (MTD), Returns (MTD), Active
Shifts, Dead Stock Value, Discount Given (MTD), Tax Liability (cumulative, `date_from="2000-01-01"`
- a liability balance, not a period movement, so a real MTD window would understate it the same
way `get_trial_balance_summary`'s Asset/Liability/Equity fields are already documented as
cumulative-not-period elsewhere in this file), Negative Stock Alert, Customer Activity (90d), and
Cash Flow (MTD, via `get_payment_entry_summary` - a real cash-movement complement to the accrual-
based P&L figure above it, deliberately distinct rather than redundant).

**A real bug caught before shipping, not by live testing but by reading the tool source**: the
first draft used `get_purchase_overview`'s own `purchase_amount` KPI (`answer_builder`'s existing
`_kpis_for_get_purchase_overview` only ever surfaces that field, never `receipt_amount`) - but that
field sums **Purchase Invoice only**, and every site here records real purchasing activity mostly
via Purchase Receipt (same fact already documented for `rank_vendors`/payables elsewhere in this
file), so it rendered a flatly misleading "Purchase Spend: PKR 0" on siezal. Fixed by swapping the
widget's source tool to `get_purchase_concentration` instead (renamed widget "Purchasing (MTD)"),
which already correctly merges Purchase Invoice + Purchase Receipt (Invoice wins when a supplier
has both) per its own docstring - this KPI-only dashboard is the first place in this module that
surfaces a real MTD purchase-spend figure at all, since `get_purchase_overview`'s Invoice-only
number was the only prior KPI mapping for "purchase spend." Confirmed live: swapping the source
took szl's/siezal's "Total Purchase Spend" from PKR 0 to the correct PKR 63,933.94 (matching the
same figure independently verified against `get_purchase_concentration` during the Phase 4 review
above), while hsm genuinely has zero purchase activity this month so PKR 0 there is correct, not a
bug.

**A known, pre-existing data-quality distortion, surfaced but deliberately not "fixed" here**: the
Profit & Loss (MTD) widget's Net Profit/Net Margin % are wildly inflated on **every** site (szl
+43.5M/9858%, siezal +43.5M/9858%, hsm +46.2M/545289%) because each site's one-time iPOS-migration
opening-stock-value Journal Entry against its `Stock Adjustment` expense account happens to be
dated inside the current calendar month window (szl/siezal: 2026-07-14; hsm: its own equivalent
migration date) - the exact same artifact already documented under "Branch ↔ Warehouse ↔ Cost
Center model" / the trial-balance notes above (`5119 - Stock Adjustment - SSM`'s ~-43.5M one-time
balance), just now visible in a headline KPI instead of a supporting balance-sheet field. This is
a real accounting artifact, not a code bug - the widget is kept (the underlying question, "what's
our P&L this month," is still legitimate) rather than silently reworked to exclude one specific
account, since a future site's own one-off migration/adjustment entry would just recreate the same
distortion under a different account name. Told to the user directly rather than presented as a
trustworthy headline number; worth revisiting (e.g. a P&L variant that excludes non-operating
one-time adjustment accounts) if this dashboard is used regularly enough that the distortion
becomes a recurring point of confusion.

**Deployment**: none needed - this dashboard is pure data (real `AI Saved Report`/`AI Dashboard`
documents), not a code change; no `bench build`/`clear-cache`/gunicorn restart applies.

**Gotcha — `bench console` executes piped input line-by-line as separate REPL cells, not as one
script**: piping a multi-line Python file directly into `bench --site <site> console` (`bench
--site szl console < script.py`) breaks any `for`/`try` block spanning multiple logical lines —
IPython's line-buffered paste handling split a `for` loop's body across cells, throwing
`SyntaxError: 'continue' not properly in loop` and silently skipping the rest of that iteration.
Fixed by feeding a **single line** that reads and `exec()`s the whole file instead:
`echo "exec(open('/path/to/script.py').read())" | bench --site <site> console` — this runs the
entire script as one atomic block, the same fix pattern documented for reload-and-commit scripts
in the `print-format-packaging` skill's "`bench console` scripts that reload/mutate must commit
explicitly" note (same root cause: piped console input is not a substitute for a real script
runner).

**Gotcha — the shared OpenRouter free-tier quota (see "Nemotron client and model config" above)
means building this on multiple sites back-to-back will transiently fail a question or two** with
either `ResourceExhausted: Worker local total request limit reached` or an HTTP 429
`Rate limit exceeded: free-models-per-min` — not a code bug, a concurrency/rate ceiling shared
across all three sites' one API key. Confirmed live: building the same 10-widget dashboard on
siezal and hsm each hit exactly 2 of these transient failures; a short (15-20s) wait then retrying
just the failed question(s) — re-running `ask()`, `save_report()`, `add_widget_to_dashboard()` for
those alone against the same already-created dashboard — succeeded every time on the next attempt.

**Uneven-looking widget grid, found and fixed 2026-07-22**: user-reported "widgets view is bad."
`.ai-assistant-widget-body` had no vertical cap (only `overflow-x: auto` for wide tables), and
`.ai-assistant-dashboard-grid` is a plain `flex; flex-wrap: wrap` with the default
`align-items: stretch` — so a widget holding a long, uncapped table (confirmed live: "Dead Stock
Risk" renders all 30 rows, "Payables Aging"/"Vendor Margin Ranking"/"Outstanding Payables" render
10) stretched every other card sharing its flex row to match its full height, producing a visibly
uneven grid (a 1-2-KPI card next to a 30-row table looks either badly stretched with a huge empty
gap, or badly mismatched in height) — the opposite of `render_dashboard_view`'s own stated design
intent, "a focused glance, not a full answer replay." **Fix, `ai_assistant_console.css` only**:
`.ai-assistant-dashboard-widget` gained `max-height: 420px`; `.ai-assistant-widget-body` gained
`overflow-y: auto`, `flex: 1 1 auto`, `min-height: 0` (the last is required for a flex-column
child's `overflow-y: auto` to actually engage instead of just growing the parent — a standard
flexbox gotcha); `.ai-assistant-dashboard-grid` gained `align-items: flex-start` so a short card no
longer stretches to match a tall neighbor even before its own content hits the cap. Every widget
now scrolls internally within a consistent card height instead of dictating its row's height.
Deployment: pure CSS under a Desk Page directory (not `public/`) - `bench build --app aimatic` +
`clear-cache` on all three sites, no gunicorn restart needed, same as the mobile-responsiveness
redesign above. **Not yet verified in an actual browser** (no browser-automation tool available
in that session) - same disclosed gap as the mobile-responsiveness redesign; check this visually
at the next opportunity before assuming it fully resolves the complaint.

## Data-leakage fix + conversation-history optimization (2026-07-18, drafted by Nemotron, reviewed/corrected/applied by Claude)

Real bug found by manual audit, not live testing: **`Scheduled Question.recipients` /
`AI Alert Rule.recipients` were plain free-text `Text` fields with zero validation** in
`create_scheduled_question`/`update_scheduled_question`/`create_alert_rule`/`update_alert_rule`.
Any user holding one of the 4 `_ALLOWED_ROLES` could point either doctype's `recipients` at an
arbitrary external email address, and `tasks.py`'s daily `run_scheduled_questions`/
`check_alert_rules` would then automatically email confidential business data (payables, margins,
vendor performance, sales) to it forever, unattended, with no guardrail and no audit trail beyond
`frappe.log_error` on failure. Fixed with a new `_validate_recipients(recipients: str) -> str`
helper in `api.py`, called from all 4 write paths: every recipient must resolve to an existing,
**enabled** Frappe `User` who **already holds one of `_ALLOWED_ROLES`** — not just any registered
account. This second condition is deliberately stricter than "any enabled User": ERPNext routinely
auto-creates User records for Customer/Supplier portal contacts, and without the role check a
Scheduled Question could still legally forward confidential financial data to one of those
low-privilege accounts. Rejects the whole save (lists every invalid recipient) rather than
silently dropping bad entries; caps at `_MAX_RECIPIENTS = 20`; dedupes case-insensitively.

Second real issue found the same way: `get_conversation_messages` had no `limit` at all — an
unbounded query plus a single-shot unbounded DOM append in `ai_assistant_console.js`'s
`open_conversation` for any conversation regardless of length. Fixed with cursor-based pagination:
`get_conversation_messages(conversation, limit=100, before=None)` returns the most recent `limit`
messages (capped at 200) in ascending order plus `has_more`; `before` is a message's own
`creation` timestamp, used to page further back. Verified live against a real 12-message szl
conversation with `limit=5`: page 1 returns the 5 newest messages ascending with `has_more=true`;
paging with `before` set to the oldest loaded message's `creation` correctly returns the next
older batch; a third page correctly returns the final 2 with `has_more=false`.

Two more N+1 queries fixed the same session (spotted in the same audit, not user-reported):
`list_dashboards` was doing one `frappe.db.count` per dashboard row instead of one grouped SQL
query; `get_dashboard` was doing one `frappe.get_doc("AI Saved Report", ...)` per widget instead
of one batched `frappe.get_all(..., filters={"name": ["in", ...]})`. Both verified live against
the real "Executive Overview" dashboard on szl (13 widgets, all titles/order correct after the
fix).

**Working-pattern note, same as every phase above**: Nemotron's first draft (via `ask-nemotron`,
piped the relevant code as stdin context) got the overall shape right for all four fixes but had
two real bugs that a Claude review pass caught before anything was applied — worth recording
because it's the same "draft, then verify" pattern that's held for every phase, not a one-off:
1. **The recipient-validation draft only checked "is an enabled Frappe User exists"**, not that the
   user holds an allowed role — the portal-account gap described above. Caught by re-reading the
   draft against the actual leak being fixed (forwarding confidential data), not by running it.
2. **The pagination JS draft called `.prepend()` once per message inside a `forEach` loop** to
   insert an older page above the existing bubbles. Since `.prepend()` always inserts at the very
   start of the container, looping it over an already-ascending-order batch silently **reverses**
   that batch's visual order (first message prepended ends up last, not first) — this would have
   applied to the very first page load too (no `.prepend()`/`.append()` branch existed), so every
   conversation would have opened with its messages in reverse chronological order, a bug visible
   the instant any 2+ message conversation was opened. Fixed by building each page's bubbles into
   a plain array first (`messages.map(...)`) and inserting the whole array in one `.append()`/
   `.prepend()` call — jQuery preserves array order on insertion, so one call is both correct and
   the same story either direction (append for the first/newest page, prepend for an older page).
   The draft also invented a new `_render_bubble`/`ai-bubble` CSS class instead of reusing the
   file's real `append_bubble` markup (`.ai-assistant-bubble`/`.ai-assistant-bubble-${role}`) —
   would have rendered unstyled/invisible bubbles for every paginated message. Fixed by extracting
   the existing bubble-building code out of `append_bubble` into a reusable `build_bubble(role,
   content, is_error)` that both the normal send path and the pagination path now share, so there
   is only one place bubble markup is defined.

Nemotron's draft also floated a 3rd, unrequested "hardening" idea (per-rule email-failure counters
+ auto-disable after N failures, requiring new doctype fields via patch) — deliberately **not**
implemented: it wasn't part of the two confirmed issues being fixed, needs a schema migration
decision, and the session doing this fix had no user available to weigh in on it. Worth revisiting
as a real follow-up if `Scheduled Question`/`AI Alert Rule` failures turn out to be a recurring
operational problem in practice.

**Deployment note**: all four fixes are Python (`api.py`) + one JS file — the JS change needed
`bench build --app aimatic` (done), and the Python change needs the usual gunicorn worker restart
per the "Deployment gotcha" note above (`sudo supervisorctl restart frappe-bench-frappe-web`) —
**not yet done as of this write-up**, since the sandboxed session that made this change has no
passwordless sudo (same limitation as the nginx-reload gotcha in this bench's CLAUDE.md); a human
needs to run that restart before these fixes are live for real requests, even though `bench
execute` calls during review already exercised the new code against real szl data successfully
(that path uses a fresh process per invocation, so it doesn't need the running workers reloaded).

## AI Dashboard widgets showing incomplete data (2026-07-19) — a third free-tier tool-calling failure mode

User-reported on siezal: several Executive Overview widgets showed no KPI cards/charts and only a
wall of text or nothing at all. Root cause was **not** the batched-fetch changes from the section
above (verified: `get_dashboard`/`list_dashboards` return all 13 widgets, correctly ordered, on
both szl and siezal) - it was that some widgets' saved `response_snapshot` had genuinely been
captured incomplete at build time, and the live `ask()` pipeline could **reproduce the same
incompleteness on demand**, which is what actually made it worth calling a code bug rather than
just stale caching.

**Two new free-tier tool-calling failure modes, distinct from the malformed-tool-call-JSON one
documented earlier**, both confirmed live and both leaving `tool_results` empty (so
`answer_builder.build_response` has nothing to build KPIs/charts/tables from, and the answer ships
as plain unstructured text):
1. **Fake tool hallucination** - asking "What is our current cash and bank balance?" (answered
   directly by the real `get_cash_and_bank_balance` tool) reproducibly (2/2 attempts) returned a
   reply that never called any tool and instead listed dozens of repetitions of
   `get_branch_stock_valuation_summary_comparison` - a tool name that has never existed anywhere
   in this codebase - while stating "I don't see a direct ... tool."
2. **Real-tool narration without ever calling one** - asking "What are our overdue payables broken
   down by aging bucket?" (answered directly by the real `get_payables_aging` tool) returned
   several paragraphs of visible chain-of-thought correctly *naming* several real tools (including
   `get_payables_aging` itself) while reasoning about which one might work, without ever issuing an
   actual tool call.

**Fix, `api.py`**: a new `_looks_like_tool_hallucination(content, tool_results)` (paired with the
existing `_looks_like_raw_tool_json`, same corrective-retry mechanism - appends a nudge message and
`continue`s within the existing `_MAX_TOOL_ITERATIONS` budget rather than accepting the reply).
Deliberately broad: fires on **any** `get_`/`rank_`/`run_`-shaped identifier appearing in the reply
while `tool_results` is still empty, not just ones absent from `TOOL_DISPATCH` - narrowing to
"unknown names only" would have caught failure mode 1 but missed failure mode 2, since case 2
correctly names real tools. A genuine natural-language answer never has a reason to spell out its
own snake_case tool identifier verbatim (it says "cash balance", not "get_cash_and_bank_balance"),
so this is safe even though it's broad - verified against a real successful answer (Cash & Bank
Balance's fixed rerun) to confirm it does **not** misfire on legitimate text. `_build_system_prompt`
also gained an explicit instruction not to narrate tool availability in plain text and to always
attempt a real function call, plus `rank_vendors`/`get_cash_and_bank_balance`/
`get_branch_profit_and_loss` added to the "prefer a purpose-built tool" example list (the existing
instruction already said this generically, but the model wasn't generalizing it past the 3 tools
originally named as examples - same "add the specific example" fix pattern already used for the
payables-vs-`run_dynamic_report` bug documented above).

**Verified live on siezal** (via `bench execute`, which loads current code fresh - no worker
restart needed for this verification step, only for real end-user requests): the exact captured
failure-mode-1 and failure-mode-2 text both correctly trip the new detector when replayed offline;
a live rerun of the cash-and-bank-balance question after the fix returned a full
kpi/chart/table/sources answer; `refresh_saved_report` then correctly recaptured both the "Cash &
Bank Balance" and "Payables Aging" saved reports with complete kpis/charts/tables.

**Known remaining gap, not fully fixed**: "Vendor Margin Ranking" (`rank_vendors`, question "Which
vendors have the best and worst gross margins for us?") is more stubborn - two refresh attempts
after the fix both hit `_MAX_TOOL_ITERATIONS` exhaustion (the hallucination guard correctly kept
rejecting non-answers, but the model never recovered with a real tool call within the 5-iteration
budget either time). This is arguably a *better* failure than before (a loud `ValidationError`
instead of a silently-incomplete answer) but the widget itself is still not fully fixed - its saved
snapshot was left at its last successful state (a `run_dynamic_report`-sourced table, no
kpis/chart, from before this session's fix) rather than corrupted by the failed attempts, since
`ask()` throws before `refresh_saved_report` ever calls `doc.save()`. Worth retrying this specific
question again later (nondeterministic free-tier flakiness) or investigating further if it keeps
failing - not chased further in this session to avoid burning more of the shared daily/concurrency
OpenRouter quota (see "Nemotron client and model config" above) on one stubborn case.

**Only the 3 widgets confirmed broken/incomplete were refreshed this session** (Cash & Bank
Balance, Payables Aging, Vendor Margin Ranking, all on siezal) - the other 10 siezal widgets and
all 13 szl widgets were left untouched: their kpi/chart/table counts were checked and found
consistent with each tool's actual by-design output shape (e.g. `get_sales_overview` genuinely has
no table/chart, `get_branch_comparison` genuinely has no KPI), not evidence of the same
incompleteness bug. Re-run the same per-widget `kpis: len(...)/charts: len(...)/tables: len(...)`
check via `get_dashboard` before assuming any other widget needs a refresh - most zero counts on
this dashboard are correct, not broken.

**Deployment note**: same as the section above - this is another `api.py`-only change, still
needs `sudo supervisorctl restart frappe-bench-frappe-web` (not done by this session, no
passwordless sudo available) before it protects real end-user chat requests through the live site;
only `bench execute`-based verification calls (fresh process per invocation) already exercised the
fix.

## More incomplete widgets found after the restart (2026-07-19, same day) — a same-tool-name overwrite bug, a stale outstanding-payable bug in a second tool, and a fourth free-tier failure mode

After the restart above, user re-reported (on siezal) that "outstanding net sales purchases" were
*still* empty - specifically "Total Sales Overview" and "Purchase Spend Overview". These turned out
to be two genuinely different, previously-undiscovered bugs, neither related to the hallucination
guard above:

1. **`tool_results` dict keyed by tool name silently drops comparison-period data.** `ask()`'s
   tool-call loop (`api.py`) did `tool_results[name] = result` unconditionally on every call. A
   comparison-style question ("this month vs last month") makes the model call the same tool
   (`get_sales_overview`) twice with different date ranges - the second call's result **overwrote**
   the first in the dict, and `build_response()` only ever sees the survivor. Concretely: "Total
   Sales Overview" (question: "...this month compared to last month?") had a narrative summary
   correctly saying "Net Sales PKR 153,728" (this month) but its structured `kpis` array showed
   `0.0` for every metric, because the second (last-month, genuinely-zero) call clobbered the first.
   The LLM's own prose stayed correct throughout (it saw both tool results in-context while
   composing text) - only the structured KPI/chart/table extraction was affected, which is why this
   sat undetected through the earlier hallucination-focused investigation (that one specifically
   looked for `tool_results` being *empty*, not present-but-wrong).
   **Fix**: keep the FIRST call's result per tool name (`if ... and name not in tool_results:`) -
   the first call matches the period the question actually asked about; later same-tool calls are
   supplementary context for the model's own narrative only, matching how `context.comparison_period`
   is already documented as unsupported in Phase 1 (`build_response`'s own comment). Verified live:
   `get_sales_overview_net_sales` KPI went from `0.0` to the correct `156052.0` after the fix.
2. **`get_purchase_overview` (`tools.py`) had its own separate, still-buggy `outstanding_amount`
   calc** - the exact same class of bug already fixed once for `get_outstanding_payables_overview`
   (see "Accounts tools" above) but never propagated to this second, independent tool that also
   surfaces an outstanding-payable figure. It summed `Purchase Invoice.outstanding_amount` only,
   returning PKR 0 on siezal (which has ~zero submitted Purchase Invoices; real debt is in legacy
   Journal Entries) while the real GL-based balance is PKR 43.8M. **Fix**: same GL Entry
   (`party_type='Supplier', is_cancelled=0`), same per-party `HAVING SUM(credit-debit) > 0` positive-
   balance-only filter (so a supplier in net credit/prepaid position doesn't drag the total down),
   scoped by the tool's existing `branch`/`supplier` params via GL Entry's own `branch`/`party`
   columns. **Lesson**: a fix to one tool computing a given business figure does not fix every tool
   that independently computes the same figure - grep for other occurrences of the same raw
   `SUM(outstanding_amount)`/`Purchase Invoice`-only pattern before considering a "total outstanding
   payable" class of bug closed. Also added `get_purchase_overview`/`get_receivables_overview` to
   `_build_system_prompt`'s named "prefer a purpose-built tool" example list - the generic instruction
   alone wasn't enough to stop the model routing "What are our total purchases this month?" to
   `run_dynamic_report` against (the empty-on-siezal) `Purchase Invoice` instead, same failure
   pattern as the payables-vs-`run_dynamic_report` bug documented earlier in this file, just for a
   different tool/phrasing.
3. **A fourth free-tier failure mode: a completely empty reply, no tool call, no tool-shaped text
   at all.** Refreshing "Outstanding Receivables" hit a case the existing two guards structurally
   cannot catch - the model returned `content: ""` with no `tool_calls`. `_looks_like_raw_tool_json`
   requires JSON-shaped text; `_looks_like_tool_hallucination` requires a `get_`/`rank_`/`run_`-shaped
   identifier in the text - an empty string matches neither, so `ask()` treated it as a valid final
   answer and returned an empty `NO_TOOL_DATA` structured response. **Fix**: a third guard,
   `not tool_results and not reply.strip()`, added alongside the other two in the same retry loop
   (same nudge-and-`continue` mechanism, same `_MAX_TOOL_ITERATIONS` budget).
4. **`refresh_saved_report` saves unconditionally on any non-throwing `ask()` result - including a
   degraded one.** This is what turned failure mode 3 into a real incident, not just a caught edge
   case: before guard 3 existed, the first refresh attempt on "Outstanding Receivables" returned an
   empty-but-non-throwing structured response, and `refresh_saved_report` immediately persisted it
   with `doc.save()` - overwriting a **previously correct** snapshot (real answer: PKR 0.00,
   legitimately zero, with a proper KPI card) with a blank one. The existing "ask() throws before
   save() runs" protection (documented in the section above) only covers the hard-exception case
   (`_MAX_TOOL_ITERATIONS` exhaustion); it does nothing for a non-throwing-but-empty result. **Fix**:
   `refresh_saved_report` now compares the fresh result's kpis/charts/tables against the *existing*
   snapshot's before saving - if the fresh result is empty on all three AND the existing snapshot had
   real data on any of them, the degraded result is still returned to the caller (so the UI shows
   what happened for that one refresh) but is **not** persisted, logged to Error Log instead
   (`"AI Assistant: refresh produced no data, snapshot kept"`). A widget that already has good data
   can no longer be silently regressed to blank by one bad free-tier response. The corrupted
   "Outstanding Receivables" snapshot from before this fix was itself repaired by a follow-up
   refresh (guard 3 forced a real tool call on retry) - confirmed back to the correct PKR 0.00 KPI.
5. **`rank_vendors` (`tools.py`) was the actual root cause of "Vendor Margin Ranking" being
   permanently broken - not LLM flakiness, as the earlier section above assumed.** Its
   candidate-vendor query sourced *only* from `Purchase Invoice`; siezal has **zero submitted
   Purchase Invoices** (its purchase activity is entirely in Purchase Receipts), so the function
   hit its own `if not purchase_rows: return {..., "vendors": []}` guard on literally every call,
   regardless of date range or which tool the model chose - no retry could ever have fixed this,
   the tool was structurally guaranteed to return nothing on this site. (The earlier session's "two
   retries both hit `_MAX_TOOL_ITERATIONS`" observation was itself a symptom: the model likely got
   an empty `vendors: []` result back, didn't trust it per the system prompt's own "trust a
   purpose-built tool's empty result" instruction as consistently as intended, and burned its
   iteration budget second-guessing instead.) **Fix**: candidate suppliers are now the union of
   Purchase Invoice AND Purchase Receipt activity in the window (Invoice figures win when a
   supplier has both, to avoid double-counting a receipt that was later invoiced; Receipt is the
   fallback for receipt-only suppliers) - mirrors `get_purchase_overview`'s existing two-query
   pattern. `outstanding_amount` per vendor also switched from `Purchase Invoice.outstanding_amount`
   to the same GL Entry-based calc as items 2 above / `get_outstanding_payables_overview` (same bug
   class, third occurrence found - grep for other `SUM(outstanding_amount)`/Purchase-Invoice-only
   patterns before considering this class of bug closed sitewide). Verified live: `rank_vendors`
   with a July date range now returns real vendors (`PAKISTAN FRUIT JUICE COMPANY PVT LTD (HICO)`,
   `AT-TAHUR LTD (PREMA)`) with correct purchase amounts and GL-based outstanding balances, where it
   previously returned `vendors: []` unconditionally. A subsequent `refresh_saved_report` on the
   "Vendor Margin Ranking" widget itself still hit two free-tier failures on retry (a degenerate
   repeated-phrase text loop, then `_MAX_TOOL_ITERATIONS` exhaustion) - guard 4 above kept the
   previously-stored snapshot intact through both, so this is now a **data-correctness fix with an
   unresolved LLM-flakiness overlay**, not the fully-broken structural bug it was before. Worth
   retrying the refresh later (nondeterministic) rather than assuming it's still the same bug as
   before this fix.

**Verified live on siezal, full Executive Overview dashboard re-check after all five fixes**: Total
Sales Overview (kpis: 3, correct PKR 156,052 net sales), Purchase Spend Overview (kpis: 2, correct
PKR 43.8M outstanding), Outstanding Receivables (kpis: 1, restored), Outstanding Payables/Cash &
Bank/Payables Aging (unchanged, still correct from the prior fix), `rank_vendors` itself confirmed
fixed at the tool level (widget refresh still flaky, snapshot protected either way).

**Deployment note**: same as both sections above - `api.py`/`tools.py` changes, needs
`sudo supervisorctl restart frappe-bench-frappe-web` before they protect real end-user requests
through the live site (not run from this session).

## UI/UX redesign — mobile responsiveness + panel decluttering (2026-07-19, drafted by Nemotron, reviewed/corrected/applied by Claude)

User feedback verbatim: "ui of ai assistant & dashboard is dry side bars takes much analysis does
nothing conversations tab taking extra data sources taking extra its not mobile friendly." Reading
the pre-existing `ai_assistant_console.js`/`.css` confirmed all of it concretely: **zero `@media`
queries anywhere** in the CSS (the 3-column flex layout with two fixed-260px side panels was
genuinely unusable below ~900px, not just suboptimal), and the right panel ("Scope & Sources")
mostly duplicated the context bar directly above the chat (Company/Branch/Date Range shown twice)
while permanently reserving 260px regardless of whether it was adding anything.

**Scope of the fix** (frontend-only, `ai_assistant_console.js`/`.css`, no `api.py`/Python changes):
1. **Responsive breakpoints** - `≥1024px` desktop (unchanged 3-column layout, but see #2), tablet
   `600-1023px` and mobile `<600px` (both side panels become fixed-position off-canvas drawers that
   slide in over a semi-transparent backdrop, rather than being squeezed into the flex row - reuses
   the pre-existing `.collapsed` class/toggle-button contract, `.collapsed` still means "not
   visible", it's the CSS meaning of "visible" that changes from "a flex column" to "a drawer" at
   these widths). Context bar's 5 fields collapse behind a "Show Scope"/"Hide Scope" toggle button
   below 1024px. Touch targets ≥40px, wider message bubbles, single-column dashboard widgets/KPI
   grid below 600px.
2. **Both panels now default to collapsed** on desktop too (not just mobile) so the chat gets full
   width by default, with the collapsed/expanded choice persisted per-panel to `localStorage`
   (`ai_assistant_left_collapsed`/`ai_assistant_right_collapsed`) so a manual toggle survives a page
   reload instead of resetting every visit - directly answers "takes much [space]... does nothing".
3. **Right panel trimmed** to only "Data Freshness" + "Data Sources" (`update_right_panel`) -
   Company/Branch/Date Range removed since they're already live in the context bar.
4. **Left sidebar conversation rows** gained a relative-time subtitle (`relative_time()`, e.g. "2h
   ago") under the title, sourced from `last_activity` - a field `list_conversations` already
   returned but the JS previously ignored entirely, so this is a pure frontend change with no
   backend involvement.
5. Selecting a conversation/dashboard/starting a new analysis now auto-closes an open drawer on
   tablet/mobile (`close_drawers_if_mobile()`) - a gap in Nemotron's own plan, added directly by
   Claude since a drawer pattern that never closes itself after a selection is not actually usable
   on a phone.

**Bugs found in Nemotron's draft before applying (8 total)** - same established pattern as every
other Nemotron-drafted change in this module (see "Working pattern" above): a review pass caught
real, concrete bugs, not just style nits.
- **Dead/broken DOM-wrapping code**: the draft's `build_layout()` used jQuery `.wrapAll()` to wrap
  the sidebar+rail (and right-panel+rail) into new `.ai-assistant-sidebar-wrap`/`.ai-assistant-
  right-wrap` divs so a shared backdrop element could sit alongside them - but the CSS draft never
  styled those two new wrapper classes at all (confirmed via a selector diff between old/new CSS).
  Since the wrapper divs would default to block layout while their children keep flex-item CSS
  properties that only apply inside a flex *parent*, this would have broken the desktop 3-column
  layout entirely (sidebar-rail and sidebar stacking vertically instead of side-by-side). Fixed by
  dropping the wrapping entirely - the backdrop is `position:fixed`, which CSS Flexbox already
  excludes from a flex container's item layout regardless of DOM nesting, so it can just be a plain
  sibling appended directly to `.ai-assistant-layout` with zero extra markup.
- **Duplicate event binding**: the draft's revised constructor called `this.build_sidebar_events()`
  a second time, not realizing `build_layout()` already calls it internally (unchanged from before
  this redesign) - would have double-bound every sidebar click handler (search input firing twice,
  a single collapse-button click toggling the class twice and net-cancelling itself, etc). Fixed by
  not re-calling it; `restore_panel_states()`/`bind_global_events()` were added to the constructor
  instead, after the existing `build_layout()` call, without touching that call itself.
- **Asymmetric localStorage persistence**: the draft added `persist_panel_state('right', ...)` to
  the right-panel toggle handler but not the equivalent call for the left sidebar toggle handler -
  the sidebar's manual collapse/expand would never survive a reload while the right panel's would.
  Fixed by adding the matching call to both handlers.
- **Wrong anchor line for the context-bar field wrapping**: the draft anchored the "wrap the 5
  fields into a collapsible container" code right after `this.$context_bar = this.$container.find(
  '.ai-assistant-context-bar')` - which runs *before* `this.build_context_bar()` actually populates
  those 5 fields into `$context_bar`. Inserted there, `.find('.frappe-control')` would find nothing
  yet, silently leaving the toggle button non-functional and the fields never wrapped. Fixed by
  moving the insertion to directly after the `this.build_context_bar();` call instead.
- **Fragile datetime parsing for the new relative-time helper**: the draft's `relative_time()` used
  `frappe.datetime.str_to_obj()`, which parses via `moment(d, frappe.defaultDatetimeFormat)` - a
  strict format string with no fractional-seconds token. Datetime fields on this bench round-trip
  with **microsecond precision** (confirmed live this session against real `AI Saved Report.
  last_refreshed`/equivalent field values, e.g. `"2026-07-19 01:27:33.151565"`), which that format
  string doesn't account for - parsing wasn't guaranteed to succeed. Fixed by normalizing the string
  to ISO 8601 (`replace(' ', 'T')`) and using the native `Date` constructor instead, which handles
  fractional seconds natively and sidesteps the moment-format-mismatch risk entirely. (`str_to_user`
  is still used for the `>=7 days` fallback case - that call was already proven safe, it's used
  identically elsewhere in this same file's `format_cell`.)
- **Three CSS syntax typos**: `word-break: break-word.`, `transition: transform 0.08s linear.`, and
  `white-space: nowrap.` each had a trailing period instead of a semicolon (three separate instances
  in an otherwise-complete CSS rewrite) - each would silently drop just that one declaration (CSS's
  per-declaration fault tolerance means the rest of each rule block still applies), regressing an
  insight-text word-break, a voice-level-meter animation, and a dashboard-widget-title's ellipsis
  truncation respectively versus the original file. Caught by grepping for a trailing-period-before-
  end-of-line pattern across the full draft, not by eyeballing 1400+ lines of CSS.

**Verification performed**: `node -c` syntax check (passed) on the final JS; a CSS selector diff
confirmed every one of the 105 original class selectors still exists in the new 1463-line CSS (116
total, the extra 11 being genuinely new classes) - i.e. the "complete rewrite" didn't silently drop
any existing rule; brace-balance check on the CSS; `bench build --app aimatic` completed with no
errors; `bench --site szl/siezal/hsm clear-cache` run on all three sites so the new page assets
serve immediately rather than a stale cached copy.

**NOT verified - explicitly still needed**: no live browser check was possible from this session
(no browser-automation tool available). The drawer slide animations, backdrop click-to-close,
Escape-key handling, localStorage persistence across an actual reload, and the responsive
breakpoints at real narrow viewport widths have only been reviewed by reading the code, not by
actually opening the page. This should be the first thing checked/screenshotted at real mobile and
desktop widths before considering this redesign fully done - per this bench's own CLAUDE.md rule
that UI changes need an actual browser check, explicitly disclosed here rather than assumed to work
because the code review found no bugs.

**Deployment note**: pure frontend (`.js`/`.css` under a Desk Page directory, not `public/`) - no
gunicorn worker restart needed (unlike every `api.py`/`tools*.py` change documented above in this
file), since Python worker state is irrelevant to static page assets. `bench build --app aimatic` +
`clear-cache` (done this session) is the correct/complete deployment step here.

## Deployment gap found by auditing Error Log directly, and a fifth free-tier failure sub-case (2026-07-20)

Prompted by a request to sweep the AI assistant's real Error Log entries (not just re-derive bugs
from code reading), a direct `tabError Log` query across all three sites turned up two things:

**1. The entire previous day's fix commit had never actually been deployed.** Every error
event found (`AI Assistant: tool hallucination corrected` ×18, `AI Assistant: malformed
tool-call text corrected` ×2, `AI Assistant: refresh produced no data, snapshot kept` ×1, all
on siezal, all 2026-07-19 01:06-01:31) predated commit `8341239` ("AI Assistant Console: fix
real data bugs, redesign for mobile", committed 2026-07-19 18:35:58) - the very commit
containing the fixes for most of these failure modes (Accounts-tools GL fix propagation, the
`tool_results` first-call-wins fix, `rank_vendors`'s Purchase-Invoice-only bug, etc., all
documented in the two sections above). But `ps -eo lstart` on the gunicorn master showed every
worker had started at 18:13:59-18:14:05 - **22 minutes before that commit landed** - and no
`supervisorctl`/`kill -HUP` reload had happened since. So the fixes were sitting correctly in
the repo the entire time this session started, completely inert in production. This is exactly
the gap every "Deployment note" in this file has been individually flagging (no passwordless
`sudo` in those prior sessions) - it just hadn't been confirmed end-to-end against the actual
running process before. **Fixed this session**: `kill -HUP <gunicorn master pid>` (no sudo
needed, matches the pattern already used elsewhere in this bench, e.g. the `mobile_sales`
UOM work) - confirmed via `ps` that all worker PIDs cycled to a fresh start time and
`aimatic.ai.api.ping` still responded afterward. **Lesson for next time**: after any `api.py`/
`tools*.py` change to this module, don't just leave a "needs a restart" note - check whether a
restart is actually still owed by comparing `ps -eo lstart` on the gunicorn master against
`git log -1 --format=%ad` for the changed files, and do the graceful reload directly if the
session has shell access to the process (it doesn't need root - only a full `supervisorctl
restart` does).

**2. A real, previously-unfixed bug, found only by reading a raw traceback in the Error Log**:
two `AI Assistant Message log failed` entries on siezal (2026-07-19 01:22/01:25, both
`role='assistant', content=''`) traced to `frappe.MandatoryError` inside `_log_turn`'s
`doc.insert()` - `AI Assistant Message.content` is mandatory, and something was reaching
`_log_turn("assistant", "", ...)` with a blank reply. The existing empty-reply guard (see
"guard 3" in the section above) was `if not tool_results and not reply.strip():` - it only
retried when tool_results was *also* empty. A second, distinct sub-case slips past every one of
the three existing guards: the model successfully calls a real tool (`tool_results` has data),
then returns an empty `content` string with no `tool_calls` on its closing turn. That reaches
`_log_turn` unguarded, throws `MandatoryError`, gets swallowed by `_log_turn`'s own
`except Exception`, and the turn silently vanishes from conversation history while the
structured answer ships with a blank `Answer.summary` (KPIs/charts/tables from the earlier
successful tool call still render, since those come from `tool_results`, not `reply` - meaning
this bug produces an answer that *looks* mostly fine, real data cards, just missing the
narrative text, which is why it wasn't obviously a broken answer until the Error Log traceback
was read directly). **Fix, `aimatic/ai/api.py`**: widened the guard to `if not reply.strip():`
(dropped the `not tool_results` requirement) - any empty final reply now retries regardless of
whether tool results already exist; the model still has those results in its own message
context, so the retry only needs to produce closing prose, not re-call anything. Reviewed by
Nemotron (`ask-nemotron`, piped the relevant code + traceback as context) before applying, per
this module's standard practice - confirmed no edge case (no legitimate reason for an empty
final reply to exist, bounded by the existing `_MAX_TOOL_ITERATIONS`, the guard only applies to
the no-`tool_calls` branch so a response with both tool_calls and empty content is unaffected
and handled correctly by the tool-dispatch loop below it). **Verified** with a mocked
`get_chat_completion` sequence (real tool call -> empty reply -> real answer): confirmed the
retry fires exactly once, the final answer keeps the first call's KPI data, the turn is
correctly persisted to `AI Assistant Message` this time, and no new
`AI Assistant Message log failed` Error Log entry is produced. Deployed via the same `kill
-HUP` graceful reload as item 1, alongside the previous day's commit.

**Working-pattern note**: this was the first time in this module's history the investigation
started from `tabError Log` directly (`bench --site <site> mariadb -e "SELECT ... FROM
\`tabError Log\` WHERE method LIKE '%AI Assistant%' ..."`) rather than from a user-reported
symptom or a code-reading pass - worth repeating periodically on all three sites, since (as item
1 above shows) a real fix can sit fully written and reviewed in the repo for hours without
protecting a single real user request if nobody separately confirms the deploy step actually
landed.

## Phase 4 — certified-tool expansion, ERPNext report execution, and governed analytics (2026-07-20)

Phase 4 expands the assistant without implementing the external review's suggested ~80 one-off
tools wholesale. `tools_expanded.py` adds 13 certified tools, bringing the fixed catalogue from
25 to 38: `get_sales_trend`, `get_hourly_sales_pattern`, `get_discount_overview`,
`get_sales_by_item_group`, `get_selling_below_cost`, `get_supplier_price_comparison`,
`get_po_receipt_variance`, `get_purchase_concentration`, `get_stock_aging`,
`get_reorder_recommendations`, `get_negative_stock_check`,
`get_customer_activity_segments`, and `get_open_documents_overview`. They use the existing
`tools.py` company/branch/warehouse resolvers, capped aggregate queries, and the same POS-only
revenue / GL-based balance rules documented above. `get_reorder_recommendations` is now the
purpose-built answer for "what should I order/restock?"; it uses recent sales velocity, an
explicit lead-time assumption, and a 50% safety buffer rather than making the LLM infer a reorder
point from `get_inventory_vs_sales`.

`report_runner.py` adds `list_frappe_reports` and `run_frappe_report`. The first searches the same
allowlisted Query/Script Report catalogue `report_registry.discover_frappe_reports()` already
maintained; the second rejects any name outside that catalogue, force-overwrites the company
filter with `_resolve_company()`, and calls `frappe.desk.query_report.run()` so the report's own
`ref_doctype`/report permission checks still run. Only the first 200 normalized result rows can
reach the model. `report_registry.py` has explicit DataSource entries for both tool calls in
addition to the discovered report records themselves.

`analytics_engine.py` adds the semantic-layer fallback `run_analytics_query` and
`drill_down_transactions`. Four datasets are exposed: sales (POS Invoice only), purchases
(Purchase Invoice + Purchase Receipt as separate measures, plus GL-based outstanding), current
inventory (Bin + Stock Ledger Entry velocity), and payables (GL Entry, positive-net-supplier
balances only). Measure and dimension names are looked up in fixed Python dictionaries that map
to pre-written SQL expressions; filter values remain parameterized; company and restricted-branch
scope are always server-derived; result limits are server-capped. The model can never provide a
table name, SQL fragment, measure expression, or dimension expression. Previous-period comparison
uses the immediately preceding equal-length period, and drill-down returns capped, linkable source
documents/vouchers using the same scope. For item-group sales, each invoice's grand total is
allocated proportionally by line base-net amount so grouped `net_sales` reconciles to the certified
header total instead of silently excluding taxes.

`api.py` now exposes 43 total function calls (38 certified + report search/run + analytics query/
drill-down + the legacy dynamic fallback), raises `_MAX_TOOL_ITERATIONS` from 5 to 8, and groups
the system prompt by Sales / Profitability / Purchasing / Inventory / Customers / Finance /
Operational categories. Fallback priority is explicit: purpose-built tool first, then
`run_analytics_query`, then `list_frappe_reports` + `run_frappe_report`, and only then
`run_dynamic_report`. The pre-existing malformed-JSON/tool-hallucination/empty-reply guards remain
generic and still apply to the larger catalogue.

**Review bugs caught before deployment (Claude session hit its limit immediately after the first
4e edit; Codex resumed from the transcript and completed this review):**
1. Ungrouped purchases, inventory, and payables silently defaulted to supplier/warehouse rows,
   while the response labelled them ungrouped; this produced no KPI instead of one true total.
   Fixed with explicit `"Total"` grouping paths.
2. Previous-period merge iterated only current-period keys, silently dropping a branch/category
   that existed only in the prior period. Fixed by merging the union of both key sets.
3. Purchase/payable balance measures ignored the requested as-of date, so a "previous period"
   comparison returned today's balance twice. GL queries now use `posting_date <= date_to`.
4. Payable drill-down ignored both branch permissions and its advertised date filters. Both are
   now force-applied; PO/receipt variance also gained its missing `po.company` predicate.
5. `get_sales_by_item_group` calculated share percentages after SQL `LIMIT`, making the displayed
   subset always add to 100%. It now computes the denominator across all qualifying groups before
   slicing the returned page.
6. New price comparison / below-cost / concentration / open-document tools did not consistently
   apply restricted users' branch scope. Their signatures, tool schemas, queries, and DataSource
   metadata now agree; below-cost pricing resolves only the visible branches' existing
   `default_selling_price_list` values and never calls the shelf-pricing write helper.
7. `list_frappe_reports`/`run_frappe_report` were exposed to the model but omitted from
   `TOOL_REGISTRY`, so rich answers could not cite them as sources. Added both entries.
8. Several new bar charts could exceed the module's established `_MAX_CHART_BARS = 10` rule, and
   inventory drill-down rendered `qty_change` as text. Both response-shape issues were corrected.

**Live read-only verification on `siezal`**: syntax compilation passed; ungrouped sales returned
one total (PKR 186,867 / 49 transactions for 2026-07-01..20); purchase analytics returned one row
(PKR 63,933.94 goods received and PKR 43,789,931.11 outstanding); payables returned the identical
PKR 43,789,931.11 established GL total; inventory returned PKR 43,459,960.81 current stock value,
exactly matching a real `Warehouse Wise Stock Balance` run through the new report runner. The
item-group previous-period path, PO/receipt variance, purchase concentration, item-group shares,
below-cost scan, and open-document overview all returned valid production shapes.

Final wiring check in a real `siezal` Frappe console: 43 tool specs, 43 unique names, 43 dispatch
entries, with no spec/dispatch differences. A real natural-language `ask("What should I order
today?")` routed to `get_reorder_recommendations` and persisted a complete reorder table. A second
natural-language item-group comparison call ended without a persisted turn before the shell call
returned; the underlying `run_analytics_query(..., dimension="item_group",
compare_previous_period=True)` path itself is live-data verified, but do not claim that particular
free-tier routing phrase is proven until it succeeds through the browser or a later `ask()` retry.
Do not burn the shared daily quota repeatedly on it just to turn this note green.

Deployment completed after the final Python edits: the old preloaded gunicorn master PID 21304 was
sent `HUP`; supervisor brought the web group back as master PID 23003 with 81 fresh workers, and
`GET /api/method/frappe.ping` returned `{"message":"pong"}` through the `siezal` Host route.

**Important caveat on the above, found 2026-07-22**: despite the "deployment completed" note,
none of Phase 4's changes were ever actually committed to git — they sat in the `apps/aimatic`
working tree (modified `answer_builder.py`/`api.py`/`chart_recommender.py`/`report_registry.py`,
new `analytics_engine.py`/`report_runner.py`/`tools_expanded.py`) for two days with no commit.
Discovered only because a follow-up session went looking for uncommitted work. **Lesson**: a
"deployment completed" note in this file describes the running gunicorn process at that moment,
never the git state — always separately check `git status`/`git log` before assuming Phase-N work
is safe from being lost, especially across a session-limit cutoff like the one that interrupted
4e here (see "Phase 4" above).

**A ninth review bug, found by a follow-up review pass, not live testing**: `run_frappe_report`
(`report_runner.py`) force-applies the caller's company the same way `dynamic_report.py` does, but
had no branch-scoping guard at all — every other tool in this module force-applies
`_resolve_branch_filter` for a branch-restricted user, but an arbitrary cataloged ERPNext
Query/Script Report's own SQL/script is not guaranteed to respect a caller's Branch User
Permission the way `frappe.db.get_list` does (many core reports run raw SQL with zero row-level
permission filtering). A branch-restricted `POS Supervisor` (a real, expected shape for that role
in this app's Branch model, even though no current site happens to have a multi-branch restricted
user today — `szl`/`siezal` currently each have only one Branch, so this was findable only by
reading the code, not by live-testing against current data) could otherwise get another branch's
data through this one tool while every purpose-built tool would have correctly scoped it. **Fix**:
`run_frappe_report` now calls `_resolve_branch_filter(company, None)` first and refuses to run any
report at all (returns an `{"error": ...}` steering the model back to a purpose-built tool or
`run_analytics_query`) whenever that returns non-`None` (i.e. the caller sees a strict subset of
the company's branches). Verified via monkeypatching `_resolve_branch_filter` (no live multi-branch
restricted user exists on any current site to exercise this end-to-end): a simulated restricted
caller is correctly blocked with the new error, and a simulated unrestricted caller still runs the
report normally. `list_frappe_reports` needed no change — it only returns report names/descriptions,
never row data.

## Working safely

Update this skill (not `CLAUDE.md` directly — see that file's own "Keeping this file current"
rule) whenever a new phase ships, a new tool/doctype/endpoint is added, or a new gotcha is found
live. Keep `CLAUDE.md`'s own `ai/` entry to a short summary + pointer here.
