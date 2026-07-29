# Known issues and risk index

Load the owning skill/reference before investigating. Update this index when
an issue is fixed, retired, or newly confirmed.

## Active operational risks

- Environment drift: old notes may call `siezal` production or `szl` test.
  Current designation is in `current-state.md`; verify runtime state.
- Deferred Posapplication behavior issues are tracked in `/home/nabeel/Posapplication/docs/known-issues.md`; re-verify before treating them as active.
- Posapplication release coupling: every `main` push publishes POS, Sales,
  Shopping and Restaurant products. See `posapplication-release`.
- POS raw REST permission history and protected RPC replacements: see
  `offline-pos`.
- FBR integration has a deliberately flagged open issue: see
  `fbr-integration`; do not fix incidentally.
- AI dashboard/tool incompleteness and model/tool-call failure patterns:
  see `ai-assistant-console/references/architecture-and-incidents.md`.
- Print-format/POS receipt selection and cache behavior: see
  `print-format-packaging`.
- Legacy migration/cutover mappings and deferred stock/pricing steps:
  see `ipos-migration` plus `apps/aimatic/ipos_data_migration/setup_szl.md`.

## Recently repaired; keep regression coverage

- Custom DocPerm POS grants could hide standard roles. Repair patches are in
  `apps/aimatic/aimatic/patches/`.
- Purchase grid header/body widths could drift during editable-grid rerenders.
- FBR submission failures must remain logged and diagnosable.
- Per-branch Foodpanda price routing and its dedicated source field must not
  regress.
- Tax Formula.gst_account can go dangling (points at a placeholder account
  that doesn't belong to the site's company) if `frappe.utils.fixtures.
  sync_fixtures` is invoked directly instead of `bench migrate` - it skips
  the `after_migrate` repair. A daily scheduled job now self-heals this
  (`aimatic.tax_formula_setup.repair_dangling_gst_accounts`), but prefer a
  full `bench migrate` over a standalone fixture sync for this app. See
  `purchase-cycle`.
- Purchase Invoice Item.custom_discount_amnt had `non_negative:1` (its PO/PR
  Item siblings are `0`), so any Purchase Invoice against a Purchase Receipt
  return - whose discount amount is legitimately negative - was blocked.
  Fixed 2026-07-29 in the fixture and live on siezal/szl/hsm. See
  `purchase-cycle`.

Do not treat this file as proof an issue still reproduces. Inspect code, Git
history, and safe runtime evidence.
