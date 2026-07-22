---
name: release-sales-apk
description: Validate, build, and release the Ai Matic Sales Android APK. Use for mobile sales ordering, UOM/search/cart/offline behavior, customer visits, promotions, signature/GPS proof, manager analytics, aimatic.mobile_sales.api changes, Sales Capacitor packaging, Sales APK/AAB requests, or verification of the published Aimatic-Sales-App artifact.
---

# Release the Sales app

Work across `/home/nabeel/Posapplication` and `/home/nabeel/frappe-bench/apps/aimatic` when the server contract changes. Read both repositories' `CLAUDE.md` guidance, then read `../posapplication-release/SKILL.md` for shared release mechanics.

## Preserve the Sales boundary

- Keep client code under `src/products/sales/` and API access behind `src/api/sales-orders.ts`, calling only `aimatic.mobile_sales.api`.
- Keep ERPNext authoritative for company, warehouse, prices, UOM conversion, stock, credit, taxes, promotions, validation, and Sales Order creation.
- Keep stable request IDs for order and visit retries. Never turn a local estimate into a confirmed total.
- Show only Item-assigned UOMs with positive conversion factors.
- Include barcode-scanner and geolocation plugins only in the Sales profile. Preserve Android coarse/fine location permissions.
- Require fresh PNG signature and GPS proof for new orders; invalidate proof after material order changes.
- Keep visits, private photos, promotions, discount approval, delivery rules, and manager analytics company/warehouse scoped and role gated.
- Keep View, Edit Draft, Exit Edit, and Cancel Order separate: View is read-only; Edit applies only to an ERPNext Draft; Exit restores any pre-existing local draft; Cancel requires a submitted order plus manager and ERPNext cancel permission.
- Persist PO reference and mobile notes through `po_no` and `Sales Order.custom_mobile_sales_notes`; normalize ERPNext workflow labels before applying mobile status filters.
- An explicit `Mobile Sales Discount Authority` row overrides the manager fallback. This makes a configured manager usable as a low-authority test salesperson while unconfigured managers retain full authority.

## Validate

Run from `/home/nabeel/Posapplication`:

```bash
npm test
npm run build
npm run android:sales:apk
```

Smoke-test OAuth login, warehouse selection, brand/category/barcode search, UOM conversion, both order views, preview/create, offline retry/idempotency, real order detail, Draft edit plus Exit restoration, permission-gated submitted-order cancellation, a pending over-authority discount, the empty approval state, visits, proof capture, and manager access. If backend schema changes, back up and migrate each target site before live API smoke checks. Do not run the Frappe test suite when the backend repository guidance prohibits it.

For deliberate pilot testing, `bench --site <pilot-site> execute aimatic.mobile_sales.demo_data.execute` creates or refreshes isolated, clearly prefixed `AIMATIC Demo` records. Never add it to install/migrate hooks, and never seed every production site automatically.

## Release and verify

Follow the shared release skill. A push to `main` releases all products, so bump the common version and validate cross-product tests. Confirm the signed asset is `Aimatic-Sales-App-<version>.apk` and verify the matching `aimatic` backend commit is pushed before rollout.
