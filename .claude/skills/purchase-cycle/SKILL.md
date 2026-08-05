---
name: purchase-cycle
description: Use for Purchase Order, Purchase Receipt, Purchase Invoice, purchase returns, supplier pricing, purchase taxes or formulas, trade offers, landed costs, procurement grids, and purchase-related Client or Server Script fixtures.
---

# Purchase cycle

Trace: `PO → PR/return → PI/return → stock, payable, tax, pricing`.

## Gotchas

- Server owns validation and calculation. Client scripts improve entry only.
- Preserve lifecycle, references, received/returned qty, cancel/amend, stock/GL
  reversal, and retry safety.
- No generic warehouse/cost-center fallback. Keep company/branch/warehouse/
  cost center/supplier/account aligned.
- Shelf/Foodpanda selling-price effects belong to `shelf-pricing`.
- Search fixtures by script name and embedded code (`client_script.json`,
  `server_script.json`, Custom Field/Property Setter), not only by filename.
- Change the smallest authoritative layer after confirming stock ERPNext behavior.
