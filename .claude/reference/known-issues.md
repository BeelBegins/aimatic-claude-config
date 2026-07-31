# Active risks

Confirm each item against current code and read-only runtime evidence before
acting. Remove it when resolved; use Git for the former explanation.

- Site-role drift: names and old notes do not prove which site is live. Use
  `current-state.md` and verify again before any impactful operation.
- Posapplication release coupling: every push to `main` publishes POS,
  Restaurant, Sales, Shopping, Windows, and Shopping web outputs.
- Older Electron terminals may still depend on narrow POS Custom DocPerm grants
  that newer clients replace with governed `offline_pos` RPCs. Confirm fleet
  versions before removing compatibility grants.
- FBR payment-mode selection uses the largest payment row. A large Gift Voucher
  row can cause the configured fallback mode to be reported instead of the
  smaller cash/card portion.
- AI results can be incomplete even when model text looks plausible. Validate
  tool selection, permission scope, bounded results, and response assembly.
- POS receipt selection is runtime state: the Electron client selects an
  enabled custom POS Invoice Print Format and does not rely on
  `POS Profile.print_format`. Confirm the active format before editing.
- Legacy cutover still depends on the tracked scripts and runbooks under
  `apps/aimatic/ipos_data_migration/`; reconcile every live pass to its source.
- Deferred Posapplication behavior risks are owned by
  `/home/nabeel/Posapplication/docs/known-issues.md`; verify them before use.
