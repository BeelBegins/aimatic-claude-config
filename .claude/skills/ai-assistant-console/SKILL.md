---
name: ai-assistant-console
description: Use for the AI Assistant Console, AI Integration Settings, model/OpenRouter/Nemotron calls, governed tools, conversational API, dashboards/widgets/KPIs, saved analyses, schedules/alerts, structured responses, or debugging incomplete/leaking AI results.
---

# AI Assistant Console

The console is governed decision support over ERP data, not an autonomous
writer. Preserve permission-aware tools, deterministic calculations,
structured responses, evidence/provenance, bounded queries and safe fallbacks.

## Load references selectively

The complete architecture, tool inventory, frontend behavior and dated
incident record is preserved in:

- `references/architecture-and-incidents.md`

Search that reference by the affected surface before editing:

- model/settings/client: `Nemotron`, `OpenRouter`, `AI Integration Settings`;
- tools/calculations: `certified`, `tools_accounts`, `revenue double-counting`;
- API/response: `structured response`, `api.py`, `conversation`;
- dashboards: `Executive Overview`, `Executive KPIs`, `widget`;
- operations: `schedule`, `alert`, `deployment gap`, `Working safely`;
- known failure modes: `data-leakage`, `incomplete`, `overwrite`, `free-tier`.

## Invariants

- Deterministic tools calculate facts; the model explains and organizes them.
- Enforce the requesting user's permissions and scope on every data path.
- Do not expose internal prompts, credentials, unrestricted SQL or data from
  another user/company/branch.
- Keep summary and drill-through separate; bound rows, dates and expensive
  replays.
- A model response is not evidence that the underlying tool returned complete
  data. Verify tool selection, arguments, results and assembly.
- Restart/reload requirements for Python and cached assets are operational
  facts; use the production gate before impactful action.

## Working path

1. Read the relevant headings in the reference.
2. Inspect current local code/diff and recent history.
3. Reproduce at the lowest deterministic layer: tool, assembler, API, then UI.
4. Validate permissions, completeness, totals and failure behavior.
5. Update the reference when a durable architecture fact or incident lesson
   changes; keep the small router focused on routing and invariants.
