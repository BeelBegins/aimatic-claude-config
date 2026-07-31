---
name: posapplication-release
description: "Use for any Posapplication product build or release request: POS, Restaurant, Sales, or Shopping APK/AAB, POS Electron/Windows, Shopping web, package versioning, pushes to main, GitHub Actions, signing, release assets, or publication verification."
---

# Posapplication builds and releases

Work in `/home/nabeel/Posapplication`. Read its current `CLAUDE.md`,
`package.json` scripts, `src/config/product-profiles.json`, and
`.github/workflows/build-release.yml` at task time. These files own product
boundaries, commands, jobs, artifact names, and required outputs; do not rely on
copied command catalogs.

## Release coupling

Treat every push to `main` as a production release of all configured products.
There is no docs-only or single-product main push. Keep unfinished, experimental,
or guidance-only work on a non-release branch. Before a release push, compare the
package version with the latest published tag and bump it so assets are not
silently replaced under an existing version. Never expose or commit signing
material, provider tokens, or environment files.

## Targeted build validation

For a build-only request, select the exact current package script for the named
product and artifact. Run the shared test gate plus only the affected product's
build/smoke checks; include Shopping web only when requested or shared Shopping
code changed. Local debug APKs are validation artifacts, not signed releases.
Expand to other products only after shared profile/auth/build code changes or a
failure indicates cross-product impact.

## Release cutoff fast path

When asked to release everything or all current changes, define the cutoff as
all legitimate non-ignored Posapplication changes present at the start, plus the
version bump. Exclude other repositories, generated/ignored output, credentials,
private keys, environment files, and clearly accidental files.

1. Capture concise status, branch, version, latest release, and diff stat.
2. Inspect changed filenames for sensitive, generated, unfinished, or anomalous
   content; inspect full patches only where needed.
3. Stage the cutoff once with `git add -A`. Review staged names/stat and run
   `git diff --cached --check`.
4. For release-only handoff after development validation is complete, use the
   workflow's mandatory test job as the release gate. Do not replay all product
   analysis or local builds.
5. Create one intentional versioned release commit and push once. Do not
   reorganize completed work during packaging unless requested.

Stop before pushing if the cutoff contains a secret, unclear accidental file,
unfinished work, or known failed validation.

## Monitor and verify

Watch the resulting workflow with concise job status/conclusion output. Fetch
detailed logs only for failed jobs, then run the smallest local validation that
addresses that failure. On success, verify the expected tag and every artifact
required by the current publish workflow; do not infer publication from a local
build or a green intermediate job.
