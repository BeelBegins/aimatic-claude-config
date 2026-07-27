# Module and knowledge ownership catalog

Use this map to select the smallest relevant skill/reference set.

| Surface | Primary code/data | Guidance owner |
|---|---|---|
| General ERP features, hooks, patches, fixtures | `apps/aimatic/aimatic/hooks.py`, `patches.txt`, `fixtures/`, DocTypes | `erpnext-feature` |
| Legacy iPOS and SZL cutover | `apps/aimatic/ipos_data_migration/` | `ipos-migration` |
| Purchase cycle and tax/trade-offer logic | purchase Client/Server Script fixtures, purchase DocType customizations | `purchase-cycle` |
| Shelf and Foodpanda prices | purchase receipt scripts, pricing modules/patches | `shelf-pricing` |
| Electron POS backend | `apps/aimatic/aimatic/offline_pos/` | `offline-pos` |
| FBR fiscalization | `apps/aimatic/aimatic/fbr_pos/` | `fbr-integration` |
| Loyalty and gift voucher | loyalty/voucher modules plus POS client flow | `loyalty-gift-voucher` |
| Branch, warehouse, cost center and finance setup | branch modules, `retail_finance_setup/`, account numbering | `erpnext-feature`, `sql-reconciliation` |
| Mobile Sales backend | `apps/aimatic/aimatic/mobile_sales/` | `oauth-client-surfaces` |
| Shopping backend/media | shopping modules and isolated media pipeline | `oauth-client-surfaces` |
| Restaurant backend | restaurant modules/DocTypes | `oauth-client-surfaces` |
| AI assistant, tools, dashboards | `apps/aimatic/aimatic/ai/` and the AI console page assets | `ai-assistant-console` |
| Reports/reconciliation | report modules, GL/Stock Ledger SQL | `sql-reconciliation` |
| Print formats | aimatic print-format module docs/templates | `print-format-packaging` |
| Desk workspaces/sidebar | workspace and sidebar module docs | `desk-navigation` |
| Sites/proxy/workers/backups | bench config and site commands | `bench-ops` |
| Client runtime/products | `/home/nabeel/Posapplication/src`, product entry points, Android/Electron config | `oauth-client-surfaces` |
| CI release pipeline | `/home/nabeel/Posapplication/.github/workflows/build-release.yml` | `posapplication-release`, `release-*-apk` |

## Data artifacts that must remain durable

- All files under `apps/aimatic/ipos_data_migration/`, including older imports,
  mapping markdown, SZL setup phases and reference data.
- Fixtures for Client Script, Server Script, Custom Field, Property Setter,
  Custom DocPerm, Workspace and related module documents.
- Patch order in `apps/aimatic/aimatic/patches.txt`.
- Dated incident explanations inside owning skill references.

When adding a new top-level module, product, migration family, or release
surface, update this catalog in the same commit.
