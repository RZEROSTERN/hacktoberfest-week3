---
paths:
  - ".github/**"
---

# CI rules

- Pin every third-party action to a **full commit SHA** with the version in a comment, and read its inputs from its
  `action.yml` at that commit instead of recalling them. Run `actionlint` on a workflow before pushing it.
- Minimal permissions: the workflow is `contents: read`. Only the one job that creates the draft release gets
  `contents: write`, and nothing else does.
- Releases are **drafts only**. No step publishes, uses `--latest` or edits a published release; the owner publishes by
  hand after the checks in `docs/RELEASE_CHECKLIST.md`. A tag is only built if it matches the app versions and is on `master`.
- Never reference a branch named "main". Production is `master`. Workflows trigger on `master`, `develop` and
  `release/*` only.
- Workflows call the repository's own scripts (`scripts/*.mjs`), so CI and `npm run dist` cannot drift; do not add build
  logic to YAML. `scripts/dist.test.mjs` fails if `build.yml` and the local command differ.
- Everything bundled is pinned with a checksum in `scripts/versions.json`. A download that does not match is deleted.
- `workflow_dispatch` only works once a workflow is on `master`, so while developing one, ask for it with a label on a
  `develop` pull request (`ci-build`, `ci-release-rehearsal`, `ci-dist-check`). Add a label only when you want the
  (long) build; a push re-runs it and cancels the previous run.
- A failing job: read the failed step's log (`gh run view <id> --job <job> --log`), fix the cause, push once. Do not
  push while another job of the same run is still useful: a push cancels the run.
