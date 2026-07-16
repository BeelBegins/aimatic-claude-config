---
name: desk-navigation
description: Adding a Desk-home tile, left-sidebar entry, or a new Page route in aimatic — Workspace vs Workspace Sidebar (two separate doctypes in this Frappe version), the parent_page top-level-tile rule, and the same-slug Workspace-vs-Page route collision. Use whenever a new standalone doctype needs Desk navigation, or a new custom Page route is being added.
---

# Desk navigation (Workspace + Workspace Sidebar)

## Two separate doctypes — a Workspace alone does not populate the left sidebar

In this Frappe version, **the left sidebar tree is rendered from a separate doctype,
`Workspace Sidebar`, not from `Workspace.content`**. Creating or editing a `Workspace` only
controls the Desk-home tile grid. If a new doctype needs to actually show up in the left nav
tree, it needs an entry in the relevant `Workspace Sidebar` record too — these are edited
together but are genuinely two different sync targets.

- `Workspace` — `aimatic/aimatic/workspace/aimatic/aimatic.json` (module `Aimatic`) is the
  Desk-home tile: header, shortcuts, then `card`/`Card Break` groups. Child-table doctypes (e.g.
  `Restaurant Order Item`) are deliberately never linked directly — matching how core ERPNext
  workspaces never link child tables either.
- `Workspace Sidebar` — `aimatic/workspace_sidebar/aimatic.json` and `.../label_printing.json`
  (one per module, matching the core convention — e.g.
  `apps/erpnext/erpnext/workspace_sidebar/buying.json`) is the actual left-nav tree, mirroring
  the same card groupings as `Section Break` rows with each doctype as a child `Link` row
  underneath. Adding a doctype to the `Workspace`'s cards without a matching `Workspace Sidebar`
  entry means it has a home-page tile but never appears in the sidebar tree — an easy half-done
  state to leave by accident.

## `parent_page` controls whether something gets its own top-level Desk-home tile

Frappe's home grid only shows workspaces with an **empty** `parent_page`. Setting
`parent_page: "Aimatic"` on a smaller workspace (as done for `Vendor Performance` and
`Label Printing`) removes its own separate top-level tile without touching anything else about
it — it stays fully reachable via the parent workspace's shortcuts. Use this instead of deleting
or restructuring an existing workspace when consolidating navigation.

## Module-doc sync — same mechanism as Print Formats, no `hooks.py` fixture entry needed

Both `Workspace` and `Workspace Sidebar` are in Frappe's native `IMPORTABLE_DOCTYPES`
(`("desk", "workspace")`, `("desk", "workspace_sidebar")` in `frappe/model/sync.py`) — picked up
automatically by `bench migrate`, exactly the same sync mechanism as Print Formats/Reports (see
the `print-format-packaging` skill for the shared mechanics: `modified`-timestamp-gated
re-import, no forced overwrite of a live Desk edit).

Icon names (`store`, `tag`, `branch`, per-item sidebar icons) are bare Lucide icon names — Frappe
strips/adds the `icon-` prefix itself. **Verify against
`apps/frappe/frappe/public/icons/lucide.svg`'s symbol IDs before using a new one** — an invalid
name fails silently (no error, just a missing/blank icon), not a thrown exception, so a typo is
easy to miss.

## Route collision: a same-slug Workspace always beats a Page

Frappe's client router resolves a top-level route segment against `frappe.workspaces` **before**
checking registered Page routes (`convert_to_standard_route` in
`frappe/public/js/frappe/router.js`) — so a Workspace and a Page can never safely share a slug; the
Workspace silently wins and the Page becomes unreachable at that URL. This is why
`vendor-performance-console` and `sales-dashboard-console` are named the way they are — deliberately
**not** `vendor-performance`/`sales-dashboard`, since those slugs are already claimed by their
respective Workspaces. The Workspace instead keeps a `URL`-type shortcut pointing at the real
`/app/<name>-console` route.

**Before naming a new custom Page's route**, check it doesn't collide with an existing or planned
Workspace slug — append `-console` (or similarly disambiguate) rather than reusing the natural
name if a Workspace of that name exists or is likely to exist.

## Working safely

Update the "Desk navigation" section of this bench's `CLAUDE.md` in the same session if a new
Workspace/Workspace Sidebar is added, an existing one is restructured, or a new Page route is
added that needs disambiguating from a Workspace slug.
