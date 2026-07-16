---
name: posapplication-release
description: Pushing to Posapplication's main branch, cutting a new POS/Restaurant/Sales/Shopping release, bumping package.json version, or anything about how the Windows installer / Android APKs / Shopping web build actually get built and published. Use before any push to ~/Posapplication's main branch, and whenever asked about release process, version bumps, or where a release artifact comes from.
---

# Posapplication release pipeline (CI-driven, not manual)

## The core fact: every push to `main` is a production release, unconditionally

`.github/workflows/build-release.yml` ("Build Desktop and Android Release") triggers on
**every push to `main`** — `on: push: branches: [main]`, no path filter, no tag requirement
(plus `workflow_dispatch` for a manual re-run of the same pipeline). There is no separate
"just a commit" vs "a real release" distinction at the CI level — pushing to `main` always
builds and publishes. Treat a push to `main` with the same care as deliberately cutting a
release, not as a routine commit.

**Do not confuse this with `npm run release`** (local `electron-builder --win nsis` +
manually invoking `scripts/publish-github-release.cjs`) — that's a fallback path only, it is
**not** the real release mechanism, and it can't even run from a Linux sandbox without Wine
(confirmed: fails here, no Wine installed). All real development for this app happens in a
Linux environment (this Claude Code sandbox); the actual Windows/Android/web builds happen on
GitHub-hosted runners via this workflow, never on anyone's local Windows machine.

## What the pipeline actually builds

Four jobs, gated behind one `test` job (`npm test`, must pass before anything else runs):

| Job | Runner | What it does |
|---|---|---|
| `windows` | `windows-latest` | `electron-builder --win nsis --publish never` (3 retries on transient packaging-download failures), uploads `dist-installer/` |
| `android` | `ubuntu-latest`, **matrix over all 4 products** (pos/restaurant/sales/shopping) | `./gradlew assembleRelease bundleRelease` per product, signed with a release keystore restored from **4 GitHub Actions secrets** (`ANDROID_KEYSTORE_BASE64`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD` — the job hard-fails if any are unset), uploads a named `.apk` + `.aab` per product |
| `web` | `ubuntu-latest` | `npm run build:shopping:web`, zips `dist-web/shopping/` into `Aimatic-Shopping-Web-<version>.zip` |
| `publish` (needs all three above) | `ubuntu-latest` | downloads every artifact, runs `node scripts/publish-github-release.cjs --require-product-apks --require-web` with `GH_TOKEN: secrets.GITHUB_TOKEN` — creates **one combined GitHub Release** with all 6 assets: the Windows `.exe` installer (+ `.blockmap` for electron-updater), 4 product `.apk` files, and the Shopping web `.zip` |

## Version bumping is not optional before a push meant to land on `main`

`scripts/publish-github-release.cjs` keys the release off `package.json`'s `version` field
(`tag = v${pkg.version}`). `getOrCreateRelease()` looks up by that tag — if it already exists,
the script **replaces the existing release's assets in place** rather than creating a new
release. Combined with "every push to `main` runs this," an unbumped version means: the next
push silently overwrites the current production release's installer/APKs under the same
version number, with no new tag, no new release notes, nothing to signal a change happened.

**Always bump `package.json`'s `version` before a push that's meant to land on `main`** if that
push should be its own distinct, identifiable release. If a push to `main` is *not* meant to be
release-worthy (docs-only, a work-in-progress commit), either bump the version anyway so it's at
least a distinct tag, or hold the change on a branch until it's actually ready — there is no
"skip the release" option once something lands on `main`.

## Local `dist-apk/` is not the release — don't confuse the two

Running `npm run android:<product>:apk` locally (dev/test iteration) writes unsigned
`*-debug.apk` files into `dist-apk/` — these accumulate across many versions as throwaway test
artifacts and are expected to be cleaned up periodically; they are **not** the signed,
CI-published release APKs. The real release APKs only exist as GitHub Release assets (named
`Aimatic-<Product>-App-<version>.apk`, no `-debug` suffix) — check
`gh release view --repo BeelBegins/Posapplication` for what's actually been published, not the
local `dist-apk/` directory.

## Working safely

- Before pushing to `main`, check `package.json`'s current version against
  `gh release list --repo BeelBegins/Posapplication --limit 1` — if they match, bump the
  version first.
- If a push is experimental/not ready for real users to auto-update into, don't push it to
  `main` — Electron's auto-updater will offer the new Windows build to real POS terminals
  once the release is published, and there's no staged-rollout gate in this pipeline.
- Update this skill and Posapplication's own `CLAUDE.md` in the same session if the workflow's
  jobs, triggers, or required secrets change.
