---
name: desk-navigation
description: Use for an aimatic Desk-home tile, Workspace, Workspace Sidebar entry, parent_page hierarchy, or custom Page route, especially when adding navigation for a DocType or avoiding Workspace/Page route collisions.
---

# Desk navigation

`Workspace` and `Workspace Sidebar` are separate module documents.

## Gotchas

- Workspace = Desk-home shortcuts/cards. Sidebar = left-nav links. Never link
  child-table doctypes in the sidebar.
- Empty `parent_page` = top-level home tile. Set it to fold under a parent
  Workspace without a separate tile.
- Native module-doc paths + bump `modified` on shipped edits. No fixture sync.
- Invalid icon symbol IDs fail silently — validate against current Frappe icons.
- A Workspace slug wins over a same-slug Page route. Disambiguate Pages with
  `-console` and point the Workspace shortcut at that route.
