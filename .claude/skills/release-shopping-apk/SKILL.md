---
name: release-shopping-apk
description: Validate, build, and release the Ai Matic Shopping Android APK and Shopping web bundle. Use for customer shopping UI, catalogue/cart/quote/checkout/order behavior, aimatic.shopping.api integration, Shopping OAuth, PWA packaging, Shopping APK/AAB requests, or verification of published Aimatic-Shopping assets.
---

# Release the Shopping app

Work in `/home/nabeel/Posapplication`. Read that repository's `CLAUDE.md`, then read `../posapplication-release/SKILL.md` for shared versioning, CI, signing, and publication rules.

## Preserve the Shopping boundary

- Keep code under `src/products/shopping/` and call only `aimatic.shopping.api`.
- Accept only customer OAuth `customer-session`; never expose employee, terminal, cost, purchasing, accounts, or administrative access.
- Show only explicitly enabled Shopping Products. Keep ERPNext authoritative for signed quotes, prices, availability, and idempotent Sales Order creation.
- Preserve Cash on Delivery and Store Pickup behavior, monotonic cart revisions, typed quantities, stale-search protection, and checkout choices across quote refreshes.
- Keep Shopping free of barcode-scanner and geolocation native plugins.
- Treat Android and the web PWA as two release surfaces of the same Shopping product.

## Validate

Run from `/home/nabeel/Posapplication`:

```bash
npm test
npm run build
npm run android:shopping:apk
npm run build:shopping:web
```

Smoke-test customer OAuth/self-registration boundaries, catalogue visibility, search/categories, cart, quote refresh, COD/Store Pickup checkout, order history, and browser callback handling. The local APK is an unsigned debug artifact.

## Release and verify

Follow the shared release skill. A push to `main` releases every product, so bump the common version and validate all tests. Confirm `Aimatic-Shopping-App-<version>.apk` and `Aimatic-Shopping-Web-<version>.zip` on the GitHub release.
