# Module ownership

Use the smallest relevant owner. A second skill is warranted only when the
requested change crosses a listed boundary.

| Surface | Primary location | Guidance owner |
|---|---|---|
| General ERP hooks, patches, fixtures | `apps/aimatic/aimatic/` | `erpnext-feature` |
| Legacy iPOS cutover | `apps/aimatic/ipos_data_migration/` | `ipos-migration` |
| Purchase documents and procurement rules | purchase fixtures/modules | `purchase-cycle` |
| Branch, MRP, Foodpanda selling prices | `aimatic/shelf_pricing/` | `shelf-pricing` |
| Foodpanda Partner API (catalog, outlet, order webhook) | `aimatic/foodpanda_integration/` | `foodpanda-integration` |
| Electron POS backend | `aimatic/offline_pos/` | `offline-pos` |
| Client OAuth and product APIs | OAuth, mobile_sales, shopping, restaurant | `oauth-client-surfaces` |
| FBR fiscalization | `aimatic/fbr_pos/` | `fbr-integration` |
| Loyalty and vouchers | loyalty/gift_voucher modules | `loyalty-gift-voucher` |
| AI console, tools, models, widgets | `aimatic/ai/`, console assets | `ai-assistant-console` |
| Reports and ledger analytics | report modules, GL/SLE SQL | `sql-reconciliation` |
| Print formats and reports | module docs, `print_layouts/` | `print-format-packaging` |
| Desk Workspaces and sidebars | workspace module docs | `desk-navigation` |
| Sites, proxy, workers, backups | bench/site configuration | `bench-ops` |
| Posapplication source products | `/home/nabeel/Posapplication/src/` | `oauth-client-surfaces` |
| Posapplication builds and publication | package scripts and CI workflow | `posapplication-release` |

Keep operational inputs in Git: migration scripts/runbooks, fixtures, module
documents, and patch ordering. Update this catalog only when ownership or a
top-level entry point changes.
