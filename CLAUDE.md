# PostCall

Local-first desktop app that turns a recorded client discovery call into a
draft proposal for freelancers. Whisper transcribes, an open-weight LLM (via Ollama) extracts
notes and drafts the proposal, everything runs on the user's machine.

- `api/` FastAPI (Python 3.12, uv, SQLModel/SQLite), `prompts/` for versioned prompts
- `web/` Nuxt 4 SPA (`ssr: false`), `desktop/` Electron shell that bundles Ollama, the api and whisper-cli
- `docs/` DECISIONS.md, BENCHMARKS.md and DEPLOYMENT.md (plan for Linux, Windows, Mac App Store; not built), `samples/` consented call recordings with key facts,
  `spike/` model benchmark scripts (not shipped; see docs/BENCHMARKS.md)

## Commands (from repo root)
- Install: `make setup` (uv sync, npm install, `.env`); `make whisper-dev` builds whisper.cpp + models
- Run everything: `make dev` (api on 8765, web on 3000); `make dev-api`, `make dev-web`
- Check Ollama: `make ollama-check`. Test / lint / typecheck: `make test`, `make lint`,
  `make typecheck` (`make format` fixes ruff). Opt-in with real models: `make test-llm` (~4.6 GB), `make test-setup` (pulls ~270 MB)
- Look at the real UI: `web/ui-check/README.md` (headless Chrome)
- Desktop: `make desktop-setup`, `make desktop-dist` (everything + `.dmg`), `make desktop-dev`, `make desktop-check`

## Git: GitFlow, no stacked PRs
- `master` is production. `develop` is integration. Never commit to either directly.
- One `feature/<name>` per build step, created from the latest `develop`.
  PR base is always `develop` (`release/*` and `hotfix/*` target `master`).
- Never branch from another feature branch. Never open a PR against anything else.
- Sequence: `git checkout develop && git pull`, branch, small commits, checks pass, push,
  `gh pr create --base develop`, `gh pr merge --merge --delete-branch`, then the next step.
- PR body: what changed, why, how tested, whether DECISIONS.md was updated.

## Workflow
- Lint + typecheck + tests must pass before each commit. Conventional Commits.
- Log every technical decision (and why) in `docs/DECISIONS.md` when made or changed.
- Check the official docs for Ollama, Whisper, Nuxt, Electron, electron-builder and
  PyInstaller instead of guessing flags or APIs. If something isn't documented, say so.
- Ask before installing anything globally or touching files outside the repo.

## Non-negotiables
- Never use a branch named "main". Production is `master`.
- No closed-model APIs or cloud inference. The only network access is model downloads the
  user approved. No analytics, telemetry or logging of transcript/proposal content.
- The user never needs a terminal or a separate install.
- The model in use always comes from local settings, never a hardcoded tag.
- Accuracy: never invent requirements, budgets, deadlines, names or commitments. Inferred
  items are labeled assumptions. Every scope item and deliverable links to its transcript
  excerpt and timestamp. Missing information goes to open questions.
- Prices come only from the freelancer's profile. A client-mentioned budget is a note.
  The summary never includes prices; pricing comes after scope.

## Gotchas
- In development Ollama runs natively on macOS (Apple GPU), not in Docker. The packaged app
  uses only its bundled Ollama, never a system one.
- Ollama pull progress is reported per layer: sum bytes across layers and never move the bar
  backwards.
- Docker holds port 8000 on the dev Mac: the api uses `127.0.0.1:8765`. Nuxt dev listens on
  `localhost:3000` (IPv6 only). The static build needs an SPA fallback to `200.html` on deep links.
- `nuxt prepare` must have run before eslint works (`npm install` does it via postinstall).
- UI text lives in `web/app/locales/*.json` (11 languages, `en.json` is the source); no raw text in templates (a test enforces it). API refusals carry a `code`.
- Prompt examples must not be in a specific language: an English one made Spanish calls come back in English.
- Hard-killing the api leaves `whisper-cli` running: stop the process tree.
- PDF export uses ReportLab's built-in font: Western European text only (others are refused, use Markdown).
- whisper.cpp reads only 16-bit WAV: convert with `afconvert -f WAVE -d LEI16@16000 -c 1`. On long
  audio, if the output is a flood of tiny segments, re-run with `-mc 0` (see docs/BENCHMARKS.md).
- Machine-specific values (RAM, pulled models, Whisper path) live in `CLAUDE.local.md`.
