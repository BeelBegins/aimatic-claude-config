---
name: desk-navigation
description: Use for an aimatic Desk-home tile, Workspace, Workspace Sidebar entry, parent_page hierarchy, or custom Page route, especially when adding navigation for a DocType or avoiding Workspace/Page route collisions.
---

# Desk navigation

Treat `Workspace` and `Workspace Sidebar` as separate module documents.

- Use Workspace content for Desk-home shortcuts/cards.
- Add the matching Workspace Sidebar section/link when the doctype must appear
  in the left navigation. Never link child-table doctypes directly.
- Leave `parent_page` empty for a top-level home tile. Set it to the owning
  Workspace when the page should remain reachable through the parent without a
  separate top-level tile.
- Keep both doctypes in their native module-document paths and bump `modified`
  timestamps for shipped edits. Do not add fixture or custom sync machinery.
- Validate new icon names against current Frappe icon symbol IDs; invalid names
  can fail silently.

A Workspace slug wins before a Page route of the same slug. Search current and
planned Workspace names before adding a Page; use a disambiguated route such as
`-console` and point the Workspace shortcut to it.

Verify the edited JSON, then migrate only an approved disposable/target site.
Confirm the home tile, sidebar entry, route destination, roles, and icon once.
Use `bench-ops` only when site migration/deployment is part of the request.
