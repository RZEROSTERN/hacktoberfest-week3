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
- Never compute or format prices in the UI: proposal text, rates and terms come from the api as written.
- After UI changes, look at the real screens (`web/ui-check/`): typecheck and unit tests do not show layout.
- A route guard holds every page behind `/setup` until the api says ready. After changing setup logic, rerun
  `web/ui-check/setup-flow.mjs`; the other ui-check flows need the setup completed once first.
- Layout is responsive: pages fill the window up to the shell's 1400px limit. `.page-grid` gives two columns when
  there is room and one when there is not (no breakpoints); a page that is one short column of text or one form
  uses `.page-narrow` (centred, 760px). The call page puts the transcript beside the proposal from 1100px up
  (`useWideScreen`). The footer stays at the bottom of the window.
- After a layout change run `desktop/scripts/layout-check.mjs` against the packaged app (its header says how): it
  opens every page at seven window sizes and fails on sideways scrolling, blank space, uncentred or unused width.
- All text a person reads comes from `app/locales/*.json` through `$t(...)` or `useFormat()`. No raw text in a
  template (`tests/i18n.test.ts` fails on it). Add a key to `en.json` first, then to the other ten files: the tests
  check that every language has the same keys and `{values}`. Never put `|`, `@` or a stray brace in a message
  (vue-i18n reads them as syntax).
- Numbers, sizes, speeds and times go through `useFormat()` (`Intl`), so no message needs a plural form.
- CSS uses logical properties (`margin-inline-start`, `border-inline-start`; never `left`/`right`) so Arabic mirrors;
  text from a call or a proposal gets `dir="auto"`. A header that does not wrap overflows off-screen in right-to-left.
- API refusals are translated by their `code` (`apiErrors.<code>` in the locale files); an unknown code shows the
  api's English text. Job errors use `error_code` the same way.
- After a UI change run `desktop/scripts/layout-check.mjs` with `LOCALES=` for the languages you touched (all eleven
  before a release): it checks layout, page language and direction, and English left on non-Latin pages.
