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

Do not treat this file as proof an issue still reproduces. Inspect code, Git
history, and safe runtime evidence.
