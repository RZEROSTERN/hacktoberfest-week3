# Decisions

Technical decisions and why, newest last. Format: what we chose, why, what we gave up.

## 2026-10-12: Scaffold

**Monorepo with `/api`, `/web`, `/desktop`.** One repo, one PR flow, and the desktop shell
needs both parts anyway. `/desktop` arrives in its own step.

**GitFlow on `master`/`develop`, never `main`.** The initial commit went directly onto
`master` (explicit exception, needed so `develop` could exist). Everything after that goes
through `feature/*` PRs into `develop`.

**API: FastAPI + uv + Python 3.12.** The machine default is 3.14, but the project pins 3.12
(`.python-version`, `requires-python >=3.12`) because the transcription and packaging
dependencies (Whisper engines, PyInstaller) are most likely to ship wheels for 3.12. Not yet
verified for each one; revisit in the model spike.

**API config: only `SCOPEWISE_*` environment variables, via pydantic-settings.** Port, data
dir, models dir, Ollama URL and CORS origins have no defaults in code, so the app fails fast
instead of silently assuming a port or the default Ollama URL (the packaged binary must not
assume anything). The only default is the bind address, `127.0.0.1`. `make dev` supplies
dev values.

**One entrypoint for dev and packaged builds: `python -m app`.** It reads the same settings
and runs uvicorn on `settings.host:settings.port`, so PyInstaller can wrap the same module.

**CORS is configurable, not open.** The Nuxt dev server (`localhost:3000`) calls the api on
another port, so the allowed origins come from `SCOPEWISE_CORS_ORIGINS`. The desktop shell
will set it for the packaged app.

**API tooling: ruff (lint + format), mypy strict with the pydantic plugin, pytest.** Small
and fast; no extra config layer.

**HTTP client: `httpx`.** Starlette's test client prints a deprecation warning suggesting
`httpx2` (a newer client from the Pydantic org). We did not adopt it: it is an unfamiliar
dependency pulled in by a warning, and `httpx` works. Revisit if the warning becomes an
error.

**Web: Nuxt 4 (latest stable, 4.6.1) in SPA mode (`ssr: false`), TypeScript strict.**
`nuxt generate` produces static files in `.output/public` for Electron to load. Verified
that generation works.

**Web package manager: npm.** Already installed; pnpm is not, and installing it globally is
not worth the time. Lockfile is committed.

**Web tooling: `@nuxt/eslint`, `vue-tsc` via `nuxt typecheck`, vitest.** `nuxt typecheck`
and `eslint` need `nuxt prepare` (runs on `npm install` through `postinstall`).

**API base URL resolution.** `useApi()` uses `window.desktop?.apiBase` when the desktop
preload provides it, otherwise `runtimeConfig.public.apiBase` (dev default
`http://127.0.0.1:8765`, override with `NUXT_PUBLIC_API_BASE`). The name `window.desktop`
is provisional; the desktop step defines the real preload contract and updates this.

**Dev workflow: one `Makefile`.** `make setup`, `make dev` (api + web together, after
checking Ollama), plus `test`, `lint`, `typecheck`, `format`. Ollama runs natively on macOS
in development so it can use the Apple Silicon GPU; it is not run in Docker.

**Dev api port is 8765, not 8000.** Docker Desktop listens on `*:8000` (IPv6) on the dev
Mac, so `localhost:8000` could reach the wrong service. Everything uses `127.0.0.1`
explicitly, and the port is only a dev default (`SCOPEWISE_PORT`); the packaged app picks a
free port at runtime.

**Ollama health check uses `GET /api/tags`.** It is documented in the official Ollama API
reference and doubles as the list of local models. We did not find `/api/version` in the
docs, so we do not use it.

## 2026-10-13: Claude Code memory

**`CLAUDE.md` is short (53 lines) and committed; scope-specific rules are path-scoped files.**
The official memory docs recommend under 200 lines and say rules with a `paths` frontmatter
field load only when Claude touches matching files. So `.claude/rules/api.md` (`api/**`) and
`.claude/rules/web.md` (`web/**`) carry the per-part rules, and `desktop.md` arrives with the
desktop step. Only what cannot be inferred from the code is written down.

**`CLAUDE.local.md` keeps the full challenge brief plus a machine-specific section.** The
plan was for it to hold only machine settings. The brief (product flow, build order) is long
and mostly useful to the person building, so it stays local rather than shipping in the
public repo; `CLAUDE.md` carries the condensed rules. Revisit if the brief should be public.

## 2026-10-13: Model spike

Numbers and caveats are in [BENCHMARKS.md](BENCHMARKS.md).

**Transcription engine: whisper.cpp (Metal), not faster-whisper.** About 6x faster on the
M2 Pro (32 min of audio in 88 s against 666 s), because faster-whisper's CTranslate2 runs on
the CPU on macOS. It also bundles as a native binary plus 6 dylibs (about 8 MB) instead of
about 330 MB of Python packages, and faster-whisper 1.2.1 crashed with the latest PyAV (needed
`av<17`). Gave up: faster-whisper decodes any audio format itself.

**Whisper model: `large-v3-turbo` quantized q5_0 (547 MiB).** The two engines' `turbo` runs
agree with each other more than either agrees with `small`, and the speed is far inside the
target (RTF 0.055). `small` is faster but disagrees most with the others. Not yet checked
against a human reference (none exists).

**Audio decoding: macOS `afconvert`, not ffmpeg.** whisper.cpp reads only 16-bit WAV.
`afconvert -f WAVE -d LEI16@16000 -c 1` ships with macOS and converted the 5-minute mp3 in
0.6 s, so no ffmpeg needs bundling (the app is macOS arm64 only). To verify: m4a and the audio
track of mp4 files; only mp3 was tested.

**Whisper flags: language `auto`, defaults first, `-mc 0` as a fallback.** On the repeated
32-minute file the default settings produced 1,487 fragments; `-mc 0` fixed that but spelled
the place names worse on the real sample ("Bofi" against "Bonfil"). The transcription step
should detect degenerate output (far too many very short segments) and re-run with `-mc 0`.

**LLM default: `gemma4:e4b` (Apache 2.0, 6.6 GB).** It is the only model that met every
target: 64 s for the 5-minute call and 160 s for the 32-minute call, 12 of 13 key facts, no
invented features, 4.6 GB resident. `qwen3.5:9b` matched it on facts but took 322 s at 30
minutes and added two small inventions; `qwen3.5:4b` and `mistral-nemo:12b` missed too many
facts; `gemma4:12b` was too slow (239 s for 5 minutes) and too terse, and on a busy 16 GB Mac
its cold load took 147 s and hung twice. First-launch download is about 7.2 GB in total.

**Recommended list in the setup wizard: `gemma4:e4b` only, for now.** The brief says every
model that meets the targets is recommended, and only one did. The others are documented as
tested but not recommended. Open question for the owner: whether to also show `qwen3.5:9b`
as an "alternative" for machines that can wait longer. Revisit when a larger sample exists.

**Notes carry text and segment ids, not model-written quotes.** Asking the model to copy a
verbatim quote doubled the output tokens and still failed: only 38 of 53 (`gemma4:e4b`) and
60 of 73 (`qwen3.5:9b`) quotes matched the transcript word for word. Dropping the quote
field cut output by about a third and e4b time by 38%, and the app now shows the cited
transcript segments, which are correct by construction. Rule for the api: never trust a
model-written quote; look it up from the segment ids.

**Notes are extracted per 8-minute chunk and merged in code.** Merging only removes exact
duplicate texts; no extra model call. On six repeats of the same call this leaves near
duplicates (paraphrases), which a consolidation step could remove. Not needed for the
targets, so it is deferred.

**Ollama call settings: `format` = JSON schema, `think: false`, `temperature: 0`,
`num_ctx: 8192`, `num_predict: 4000`.** The schema is also pasted into the prompt, as the
Ollama structured-outputs docs recommend. `think: false` is the documented way to switch
thinking off; `gemma4:12b` is the only model that was not tried with thinking on. Pydantic
validation never needed the retry in these runs.

**Open questions need a deterministic backstop.** In the 5-minute run `gemma4:e4b` asked
neither about the budget nor the deadline. In the proposal step, when the notes contain no
budget or deadline, the code should add those open questions itself instead of relying on the
model.

**Accuracy checks that run in code (kept for the proposal step).** Segment ids must exist,
every scope item and deliverable needs a source or an assumption flag, every number in the
investment section must appear in the freelancer's profile, and the summary must not contain a
price (money patterns only; a plain digit check flags street numbers). The wrong
"out of scope" item that `gemma4:e4b` produced in the 32-minute run shows model output also
needs the source link to be reviewable.

**Spike scripts live in `spike/` with their own uv project.** It pulls faster-whisper,
onnxruntime and PyAV, which the api must not depend on. Prompts there (`notes_v1.md`,
`notes_v2.md`, `proposal_v0.md`) are experiments; the api will get its own versioned copies
under `api/prompts/`.

**The key facts file is a draft written from a Whisper transcript.** A model cannot hear the
audio, so a person who was on the call must confirm it. The fact counts in BENCHMARKS.md are
provisional until then.

## 2026-10-13: Transcription

**A recording is a `call`; its job state lives on the same row.** `POST /calls` uploads,
`GET /calls/{id}` returns status and progress, plus `transcript`, `cancel`, `retry` and
`DELETE`. A separate jobs table would add nothing while there is one job per call. Statuses:
queued, converting, transcribing, done, failed, cancelled.

**Progress is polled once a second, not streamed.** One small JSON request is the simplest
thing that works for one running job. Server-Sent Events stay reserved for model downloads
(step 8), where the brief asks for them.

**One transcription at a time.** A single worker thread runs the queue. Whisper is heavy, a
second parallel run would only slow both, and the owner asked to keep other jobs usable.
whisper.cpp uses 4 threads by default (`SCOPEWISE_WHISPER_THREADS`).

**Uploads are streamed to disk and named by id.** Allowed extensions: mp3, m4a, wav, mp4. The
file lands at `<data_dir>/audio/<id>/original.<ext>`; the user's file name is kept only as a
display title (path parts removed) and is never logged.

**Audio retention.** Deleted as soon as the transcript is saved, unless "keep the audio" was
ticked. Kept when the job fails or is interrupted, so Try again works without re-uploading
(deleted after a successful retry or when the call is deleted). Deleted when the user cancels.
The temporary WAV is always deleted.

**Progress comes from `whisper-cli -pp`, never goes backwards, and stops at 99% until saved.**
If the `-mc 0` re-run starts, the bar holds at its last value instead of restarting.

**Degenerate-output guard.** A transcript with at least 20 segments where more than 40% have
two words or fewer is re-run once with `-mc 0`. Thresholds come from the spike: the broken run
had 69% such segments, every healthy run 15% or less.

**Whisper paths are plain optional env vars for now** (`SCOPEWISE_WHISPER_CLI`,
`SCOPEWISE_WHISPER_MODEL`). The api starts without them and a job fails with "engine/model
missing". Step 8 replaces the model path with the model chosen in local settings.

**Audio decoding verified for mp3, m4a, wav and audio-only mp4.** The integration test makes
AAC m4a and mp4 files with `afconvert` and transcribes them. An mp4 that contains video is not
tested (no tool here can make one).

**Process lifecycle.** A clean shutdown (SIGTERM) or a cancel kills `whisper-cli`, checked
with the real binary. A hard kill of the api (SIGKILL) would leave `whisper-cli` running until
it ends on its own, so the desktop shell must stop the whole process tree. On the next start,
jobs found running are marked failed with `interrupted` and keep their audio.

**SQLite in WAL mode, tables created on start, no migrations yet.** The schema may still
change before the first release, and there is no user data to preserve, so a migration tool
is deferred.

**Tests.** Unit tests use a fake decoder and transcriber, and a stand-in `whisper-cli` script
so the real subprocess code (progress parsing, cancel, crash, `-mc 0` re-run) is exercised
without a model. One integration test runs `afconvert` and whisper.cpp on a 20 s clip as wav,
m4a and mp4 with the small `base` q5_1 model (60 MB) and is skipped when the engine or model is
missing.

**Web.** The upload uses XMLHttpRequest because `fetch` cannot report upload progress, and it
can be cancelled. Transcript lines have ids `segment-<id>` so source links can jump to them
later. The UI has not been looked at in a browser: no browser tool was available.

## 2026-10-13: Notes and proposal generation

**The code writes the money, the model writes the words.** The investment section is built from
the profile's rates (copied as written, in any currency) and the terms are the profile's payment
terms. The model never receives the rates, so a price cannot come from it; a test checks that
neither the prompt nor the request contains them. The client's budget, if the call has one, is
shown in the investment section as a labelled note with its source, never as the price. Any
amount of money in the model's narrative text is a hard error.

**Validation, retry and repair.** Every answer is parsed with Pydantic and checked. On any
problem the request is sent once more with the problems listed. After that: unknown or missing
sources are repaired in code (invalid ids removed; an item left with none is dropped from the
notes, or kept in the proposal flagged as an assumption), while a price in the text or an empty
summary fails the draft with a clear error (`draft_invalid`) and nothing is stored. A schema
failure twice gives `invalid_model_output`. Counts of repairs are kept as warnings.

**Sources are segment ids, checked per chunk.** Each notes item cites the ids of the segments it
comes from, and a chunk may only cite its own segments. The quote and timestamp shown when the
user clicks a source are looked up from the stored transcript when the draft is read.

**Notes groups.** client, client context, problem, goals, requirements, constraints, budget,
deadlines, next steps, risks, open questions. Promised next steps ("I'll send a prototype in
two weeks") are kept apart from deadlines: with one list, the code thought a delivery date had
been discussed and skipped the question. The list of groups is derived from the model so the
merge, check and repair code cannot miss a new one (an earlier version did, and it was only
noticed by reading a real run).

**Fixed backstops in code.** If the call states no budget, "what budget does the client have in
mind?" is added to the open questions; same for the delivery date. With no deadline and no next
step the timeline section says the call did not cover one, whatever the model wrote. The notes'
own open questions are not copied into the proposal (the model carries over the useful ones in
the proposal language; copying them produced duplicates in two languages).

**Fixed wording is localized for six languages** (en, es, pt, fr, de, it): section titles, the
price sentence, the budget label, the timeline fallback and the two questions. Other
languages fall back to English for those fixed strings only; the model's own text is always in
the requested language. Pricing is always placed after the scope, whatever order the profile asks
for.

**Profile and settings storage.** A single-row `profile` table (name, services, hourly rate,
project rates, payment terms, preferred sections, tone), with `GET/PUT /profile`. The screen
comes in the next step. A key/value `appsetting` table holds the language model in use
(`llm_model`). `SCOPEWISE_LLM_MODEL` only seeds it when it is empty; the code reads the tag from
the table on every request and contains no model tag. The Makefile seeds `gemma4:e4b` for
development.

**Drafting shares the single worker with transcription**, so Whisper and the language model never
run together on a 16 GB Mac. One draft per call; regenerating replaces it. Jobs found running at
start are marked interrupted.

**Ollama is called through `/api/chat` with streaming**, so a cancel stops generation as soon as
the next token arrives (not while a cold model is still loading, which can take up to a couple of
minutes). Settings: JSON schema as `format`, `think: false` (retried without it for models that
reject it), temperature 0, `num_ctx` 8192, and `keep_alive` 1 minute so the model frees its
memory soon after a draft.

**Prompts** are `api/prompts/notes_v3.md` and `proposal_v1.md`, mention no model, and are found
next to the `app` package (override: `SCOPEWISE_PROMPTS_DIR`), so the packaged binary must bundle
the folder beside `app`. Lessons from three revisions on the sample call: asking for
self-contained third-person statements fixed a misread "out of scope" item, and writing the
proposal items "in the proposal's voice" stopped them reading like quotes. An English example
inside the prompt pulled the notes into English even for a Spanish call, so examples must not be
written in a specific language.

**Result on the sample call with `gemma4:e4b` (the only model used in this step).** 40 to 92 s
for notes plus proposal depending on whether the model was cold (target: under 3 minutes); 12 of
13 key facts; no invented feature; correct out-of-scope items; no price outside the profile; no
repairs needed. Still imperfect: the contact-information requirement is missed, one open
question can restate something the interviewer asked, and spelling mistakes in the transcript
("Cacún", "Bofi") flow into the proposal. One sample and a few runs; the result is not stable
between prompt revisions.

**Tests.** The model is scripted in unit tests (retry, repair, hard failure, cancel, chunking,
languages, sections, privacy of logs, no model tag in code). `make test-llm` runs the real model
on the sample transcript and is opt-in because it loads about 4.6 GB into memory; plain
`make test` never does.

**No screen yet.** This step is API only. The profile screen and the generate button with
progress and cancel come next, then the editor with source links.

## 2026-10-13: Profile screen and the draft in the UI

**Profile form.** Name, services (one per line), hourly rate and project rates as free text in
any currency, payment terms, tone, and the preferred sections with up/down buttons. The form
mirrors the API rule that pricing always comes after the scope: the investment row cannot be moved
above scope. Saving "all sections in the default order" stores an empty list, which means the
default. The UI never builds or formats a price: rates reach proposals exactly as typed.

**Draft panel on the call page.** Language choice (default: the call's language), Draft proposal,
a progress bar with plain labels ("Reading the call (part 2 of 5)", "Writing the proposal"), and
Cancel. Cancelling takes as long as the model needs to produce its next token (33 s measured
while the model was still loading), so the button switches to "Cancelling…" at once. Failed drafts
show the API's plain-language message and Try again; Draft again asks before replacing a finished
draft.

**Source links.** Every item with sources shows a chip per source with its time. Clicking a chip
opens the quote from the call with its timestamp; "Show in transcript" opens the transcript,
scrolls to that segment and highlights it. Items the model could not source are marked
"Assumption". A second view, "What the draft is based on", lists the notes the same way. This is
read-only: editing and export are the next step.

**The UI was verified in a real browser this time.** `web/ui-check/` drives the installed Google
Chrome headlessly over the DevTools protocol (no installs, no dependencies) and saves screenshots.
It covered the profile flow, the real-model draft with cancel and source links, a phone-width
layout and the production static build; no console errors. Unit tests cover the helpers (section
order, form conversion, labels, error messages).

**Static build and routing.** `nuxt generate` writes only `index.html`, `200.html` and `404.html`,
so a plain static server answers 404 on `/profile` or `/calls/<id>`. With a fallback to `200.html`
everything works, including deep links. The desktop shell must do the same, or the app should use
hash routing; decide in the desktop step. The Nuxt dev server listens on `localhost:3000` over IPv6
only, which is why the api's allowed origins include `localhost`.

**Known limits of the draft view.** A real run on the sample put the interviewer's slip "menú de
facturación" into scope and deliverables, and one open question repeated an interviewer question.
Both are sourced, so the user can see where they came from and remove them in the editor.
