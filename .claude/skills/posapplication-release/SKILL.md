---
name: posapplication-release
description: "Use for any Posapplication product build or release request: POS, Restaurant, Sales, or Shopping APK/AAB, POS Electron/Windows, Shopping web, package versioning, pushes to main, GitHub Actions, signing, release assets, or publication verification."
---

# Posapplication builds and releases

Work in `/home/nabeel/Posapplication`. Read its `CLAUDE.md`, `package.json`
scripts, `product-profiles.json`, and `.github/workflows/build-release.yml` at
task time — they own commands and artifacts.

## Gotchas

- Every push to `main` releases all products. Guidance-only or unfinished work
  stays on a non-release branch.
- Bump package version vs latest published tag before a release push so assets
  are not silently replaced.
- Never expose or commit signing material, provider tokens, or env files.
- Build-only: run shared tests plus only the named product's build/smoke.
  Local debug APKs are not signed releases.
- Release cutoff: stage once, review staged names, one versioned commit, one
  push. Stop if secrets, accidental files, or unfinished work are in the cutoff.
- Watch CI concisely; fetch detailed logs only for failures. Verify the tag and
  every expected artifact — a green intermediate job is not publication.
