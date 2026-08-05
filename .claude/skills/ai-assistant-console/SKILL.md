---
name: ai-assistant-console
description: Use for the AI Assistant Console, AI Integration Settings, OpenRouter or Nemotron calls, governed tools, conversational API, routing, structured responses, dashboards, widgets, KPIs, saved analyses, schedules, alerts, or incomplete and leaking AI results.
---

# AI Assistant Console

Governed decision support, not an autonomous ERP writer. Entry points:
`ai/api.py`, `routing_engine.py`, `tools*.py`, registries, `answer_builder.py`,
response schemas/quality modules, `nemotron_client.py`, `tasks.py`, console UI.

## Gotchas

- Scope every tool to the requesting user's permissions, company, branch,
  warehouse, role, and date range. No unrestricted SQL, other-user data, or
  credential leakage.
- Deterministic tools own facts and totals; the model selects, explains, and
  summarizes. Do not ask the model to recreate governed query results.
- Tools stay allowlisted, typed, row/date bounded, timeout-aware, and read-only
  unless a separately approved write design exists.
- Load provider keys server-side. Sanitize provider failures; never return
  request headers or tokens to the client.
- A fluent model answer is not proof of completeness. Trace route → tool args →
  results → schema → quality checks → API → UI. Keep explicit partial/failure
  states; do not overwrite a complete deterministic result with an empty fragment.

Use `sql-reconciliation` only when the change adds substantial ledger SQL.
