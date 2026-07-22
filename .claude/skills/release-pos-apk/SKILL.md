---
name: release-pos-apk
description: Validate, build, and release the Ai Matic POS Android APK or POS Electron client. Use for changes under POS renderer/core/database/mobile code, Android POS packaging, POS APK/AAB requests, Windows POS releases, or verification of the published Aimatic-POS-App artifact.
---

# Release the POS app

Work in `/home/nabeel/Posapplication`. Read that repository's `CLAUDE.md`, then read `../posapplication-release/SKILL.md` for the shared versioning, CI, signing, and publication workflow.

## Preserve the POS boundary

- Keep Electron POS-only. Do not import Restaurant, Sales, or Shopping screens into the POS renderer.
- Keep ERPNext and `aimatic.offline_pos` authoritative for final prices, stock, accounting, FBR submission, refunds, loyalty, and gift vouchers.
- Keep Electron terminal-token authentication separate from Android POS enrollment and employee OAuth2 PKCE.
- Include the barcode-scanner plugin for Android POS. Do not add Sales-only geolocation.
- Preserve the durable offline sale queue and never allow offline refunds, close-shift, or customer creation.

## Validate

Run from `/home/nabeel/Posapplication`:

```bash
npm test
npm run build:pos:electron
npm run android:pos:apk
```

The local APK is an unsigned debug artifact in `dist-apk/`; it is not the production release. Exercise affected POS flows, especially online/offline sale, receipt, refund, cashier login, shift lifecycle, and updater behavior when relevant.

## Release and verify

Follow the shared release skill. A push to `main` releases every product, so bump the common version and validate cross-product tests before pushing. Confirm the signed GitHub asset is named `Aimatic-POS-App-<version>.apk`; the Windows installer is `Aimatic-POS-App-Setup-<version>.exe`.
