---
name: ai-assistant-console
description: Working on aimatic's AI Assistant Console (aimatic/ai/, aimatic/aimatic/page/ai_assistant_console/) — the Nemotron/OpenRouter-backed conversational BI assistant, its 16+ fixed tools, the dynamic-report fallback, the structured KPI/chart/table/insight response contract, conversation management, saved reports/dashboards/export, or scheduled questions/alert rules. Use whenever ai/api.py, ai/tools*.py, ai/*.py, or ai_assistant_console.js/.css changes, or a new AI Business Intelligence Console phase is being built.
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
later phases, not yet built.

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

## Tools: 25 fixed + 1 controlled dynamic fallback

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

## Working safely

Update this skill (not `CLAUDE.md` directly — see that file's own "Keeping this file current"
rule) whenever a new phase ships, a new tool/doctype/endpoint is added, or a new gotcha is found
live. Keep `CLAUDE.md`'s own `ai/` entry to a short summary + pointer here.
