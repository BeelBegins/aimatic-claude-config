---
name: ai-assistant-console
description: Use for the AI Assistant Console, AI Integration Settings, OpenRouter or Nemotron calls, governed tools, conversational API, routing, structured responses, dashboards, widgets, KPIs, saved analyses, schedules, alerts, or incomplete and leaking AI results.
---

# AI Assistant Console

Treat the console as governed decision support, not an autonomous ERP writer.
Inspect current entry points before editing: `ai/api.py`, `routing_engine.py`,
`tools*.py`, registries, `answer_builder.py`, response schemas/quality modules,
`nemotron_client.py`, `tasks.py`, and the console/dashboard assets that consume
their output.

## Boundaries

- Enforce the requesting user's document permissions, company, branch,
  warehouse, role, and date scope on every tool and drill-through path. Never
  expose another user's data, internal prompts, unrestricted SQL, or credentials.
- Let deterministic tools calculate facts; use the model to select, explain,
  organize, and summarize. Do not ask the model to recreate totals already
  available from governed queries.
- Keep tools allowlisted, typed, row/date bounded, timeout-aware, and read-only
  unless a separately approved write design exists. Separate cheap summaries
  from explicit drill-through.
- Load provider keys and model settings server-side. Sanitize provider failures
  and never include request headers or tokens in client responses or logs.

## Response completeness

Follow the path from route selection through tool arguments/results, invocation
assembly, structured schema, response-quality checks, API serialization, and UI
rendering. A fluent model answer is not proof that all tool rows, widgets, or
evidence survived. Preserve explicit failure/partial states; do not overwrite a
complete deterministic result with an empty model fragment.

## Verify narrowly

Reproduce at the lowest deterministic layer first: tool, assembler/schema, API,
then UI. Check one allowed scope and one denied/cross-branch scope, independently
reconcile calculations, force empty/partial/provider-failure behavior, and
confirm the final structured response is complete. Expand to schedules, alerts,
or dashboards only when shared code changed. Use `sql-reconciliation` as a
second skill only when the requested feature introduces substantial ledger SQL.
