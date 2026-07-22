---
name: release-restaurant-apk
description: Validate, build, and release the Ai Matic Restaurant Android APK. Use for Restaurant waiter UI changes, aimatic.restaurant.api integration, tables/menu/orders/KOT behavior, Restaurant Capacitor packaging, Restaurant APK/AAB requests, or verification of the published Aimatic-Restaurant-App artifact.
---

# Release the Restaurant app

Work in `/home/nabeel/Posapplication`. Read that repository's `CLAUDE.md`, then read `../posapplication-release/SKILL.md` for shared versioning, CI, signing, and publication rules.

## Preserve the Restaurant boundary

- Keep code under `src/products/restaurant/` and API calls behind `src/api/restaurant.ts` using only `aimatic.restaurant.api`.
- Keep the public employee OAuth2 PKCE flow; do not accept POS terminal credentials or generic ERPNext Resource API access.
- Keep live server state separate from `mock-data.ts`. Explore Demo must never submit data or be presented as a live workflow.
- Treat kitchen status as read-only for waiters. Do not silently activate visual/deferred transfer, split-bill, scanner, or POS Invoice actions.
- Do not include barcode-scanner or geolocation native plugins unless a real Restaurant workflow is implemented and reviewed.

## Validate

Run from `/home/nabeel/Posapplication`:

```bash
npm test
npm run build
npm run android:restaurant:apk
```

Smoke-test OAuth login, profile/floor/table loading, live menu prices and stock, order creation/update, modifiers, KOT dispatch, and strict demo isolation. The local APK is an unsigned debug artifact only.

## Release and verify

Follow the shared release skill. A push to `main` releases all products, so bump the common version and validate the whole suite. Confirm the signed asset is `Aimatic-Restaurant-App-<version>.apk`. Do not describe deferred UI actions as working release features.
