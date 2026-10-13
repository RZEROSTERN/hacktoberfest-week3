---
paths:
  - "web/**"
---

# Web rules

- SPA mode only: no server routes or SSR-only features.
- API base URL comes from the desktop preload when present, otherwise runtimeConfig
  (`useApi()` already does this).
- Composables handle API calls; components stay presentational.
- Long jobs (downloads, transcription, generation) always show progress and can be cancelled.
- Source links on every scope item and deliverable. Assumptions are visually flagged.
- UI text in English; proposal content in the call's language.
