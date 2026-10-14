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

## 2026-10-13: Editor and export

**What can be edited, and the rules that still apply.** The narrative sections (summary, problem,
timeline, terms) are text boxes; scope, deliverables and out of scope are lists of items; open
questions and the investment rates are lists of lines. The api (`PUT /calls/{id}/draft/proposal`)
enforces the accuracy rules on every save, so they hold whatever the client sends:
- Prices are refused everywhere except the investment section and the terms. The summary message
  says so explicitly. The freelancer may write their own rates in the investment section: the
  price then comes from the freelancer, never from the model or the client.
- Source ids must exist in the transcript.
- An item with no source is always an assumption, whoever wrote it. The user cannot clear that
  flag, so an item the user adds is flagged too; a sourced item can be flagged by hand.
- A refused save changes nothing (all or nothing).
The editor keeps each item's source chips, so the quote is one click away while editing.

**Unsaved changes.** Save is disabled until something changes, leaving the page with unsaved
changes asks first, and "Draft again" warns that it replaces the current draft including edits.
Downloads always use the saved version and say so.

**The export is client-facing.** No timestamps or quotes. Items the call did not support carry
"(to be confirmed)" in the proposal's language, so an assumption is never presented as something
the client said. The client's budget note is included under the rates with its label; the
freelancer can delete it in the editor first. Empty sections are left out, sections follow the
profile's order (pricing after scope), and the title is "Proposal — <client>" with the
freelancer's name underneath. The file name is ASCII (`propuesta-trevos.pdf`).

**PDF with ReportLab (BSD), Markdown by hand.** The PDF is built in the api so dev and packaged
builds share one path and no browser or system library is needed (WeasyPrint needs Pango and
Cairo; fpdf2 is LGPL). ReportLab is pure Python plus Pillow and charset-normalizer, and uses the
built-in Helvetica. Consequence: text outside Western European languages (for example Polish
"ł" or Chinese) would print as boxes, so the PDF export refuses it with a plain message and the
user is pointed to Markdown. All six languages with translated fixed wording (en, es, pt, fr,
de, it) are covered. Page size is A4 for now (a Letter option could come later; Mexico and the US
use Letter). `pypdf` (BSD) is a test-only dependency used to read the PDFs back. For the
desktop step: bundle ReportLab and Pillow, and list ReportLab (BSD), Pillow (HPND) and
charset-normalizer (MIT) in the third-party notices.

**Downloads go through `fetch`, not a link.** A link to a refused export (for example the PDF
with unsupported characters) would open raw JSON in a tab; fetching it shows the api's message
in the page. This needs `Access-Control-Expose-Headers: Content-Disposition` so the browser can
read the file name: a first version silently saved files as `proposal.md` because the header was
hidden; a real download in the browser check showed it, and a test now covers it.

**Verified in the browser** (`web/ui-check/edit-flow.mjs`, 21 checks): editing, removing and adding
items, a price refused with a message, saving and reloading, the unsaved-changes guard, real
Markdown and PDF downloads with the right names, a refused PDF shown as a message, source links
inside the editor, and no horizontal scroll at phone width. The PDF was also rendered with macOS
Quick Look and looked at.

## 2026-10-13: First-launch setup and model management

**What the user is offered.** The list is a versioned file, `api/data/models.json`, built from
BENCHMARKS.md: for each model its size, the memory it needs, its license and a note on speed and
quality. Only `gemma4:e4b` is recommended and preselected (the earlier open question: the others
are shown, unselected, under "Other models we tested", with their notes). A model whose memory
need is more than the computer's total is badged "Not recommended for this computer" and can
still be picked, with the numbers shown (on this 16 GB Mac only Gemma 4 12B is flagged). The
memory figures are our estimates from the benchmark runs, not measurements on other machines.
An "Advanced" field takes any Ollama name and tag, with a link to the Ollama library and a note
that untested models may give lower quality.

**The speech model is pinned.** The catalog URL points to one Hugging Face revision (not a moving
branch) and carries the size and SHA-256. The checksum was cross-checked against the one Hugging
Face publishes for the file (`x-linked-etag`) and against the file used in the spike. A real
download through the app's own downloader: 574 MB in 11 s, checksum verified.

**Six steps, one run.** Prepare the engine (wait up to 30 s for Ollama; the desktop shell starts
the bundled one before the api), language model, speech model, verify, check the model works,
ready. Steps with nothing to do (already on this computer) are marked and count for little in
the overall bar. The bar is a weighted sum (the two downloads and the check weigh most) and never
moves backwards. The same run serves the first launch, switching to another model and downloading
a new one from Settings.

**Names.** Checked locally (shape, and cloud models are refused: `gemma4:cloud` and
`...-cloud` would send calls to Ollama's servers). Whether a model exists is left to Ollama,
which answers a pull for an unknown name inside the stream (`pull model manifest: file does not
exist`) before any bytes move; the docs do not say this, it was observed on Ollama 0.35.1, as was
HTTP 400 `invalid model name`. After a pull, a model that Ollama lists with a `remote_host` is
deleted and refused.

**Progress for a pull sums all layers and never goes back.** Ollama reports one layer at a time:
the weights first, then a few tiny layers that each start at 0. The app sums completed and total
over the layers seen and keeps the highest of each. Verified on the real Ollama that after a
disconnect the next pull starts from the exact byte where the first one stopped (92,888,266 bytes
in the test), although the docs do not promise resuming.

**Pause, failure, and closing the app.** Pause stops the transfer and keeps what has arrived (the
`.part` file, Ollama's layers). A network error ends in "failed" with a retry that continues. A run
found running at start (the app was killed or quit) becomes "interrupted": it is offered, never
resumed silently, because downloading is the user's decision. After a restart the speech model's
progress is read from the file on disk, not from the last saved value (saves are throttled to every
2 s, and a browser check showed the saved value was up to 100 MB behind).

**Whisper download.** HTTP range requests resume from the size of the `.part` file; a server that
ignores the range restarts from zero; a finished `.part` that was never renamed is completed
without downloading again; the file is only moved into place after its size and SHA-256 match, and
is deleted on a mismatch. Data is written in 64 KiB chunks: with 1 MiB chunks a connection that
dropped early left an empty file and lost up to 1 MiB.

**Disk space.** Needed = what is still to download plus 1 GiB of room, checked before anything
starts. A model outside the catalog has no known size, so it is checked as soon as its first layer
reports one. The screen shows needed and available, and disables "Download now" when short.

**The compatibility check runs the real task.** The model gets a short built-in English call
through the app's notes prompt and schema. It passes when the notes are valid, their sources
exist and there is a problem, a goal or a requirement to build on. Output is capped at 1,200
tokens: a model that rambles past that is failing, and the cap turned a 5-minute failure into a
45-second one. Real runs: `smollm2:135m` fails (`compat_invalid_output`), `gemma4:e4b` passes. It
cannot judge quality beyond that: structured output is constrained, so any chat model returns
valid JSON, and "found something useful" is the part that catches too-small models. A failing
model stays downloaded but is not activated; the screen offers the recommended model and a way to
choose another.

**Settings.** Lists the models on the computer (in use first), with "Use this model" for ones
already checked, "Check and use" for the rest (the same run, skipping downloads), delete (never the
one in use), "Download another model" (the same picker) and the speech model with delete. Deleting
the speech model sends the app back to the setup request.

**Nothing works before setup.** A route guard sends every page to `/setup` until the api reports
ready (models present, selected model installed and checked, speech model whole). "Not now" shows a
page that says so and the request returns on the next launch. The web page cannot close the window:
the desktop shell decides what "Not now" does there. If the engine is not answering, the page says
so instead of asking for downloads.

**Progress stream.** `GET /setup/events` sends Server-Sent Events when the snapshot changes
(speed and time left make it change about twice a second while downloading) and ends when the run
does. The web app falls back to polling every 2 s if the stream cannot open.

**Development goes through the same setup.** `make dev` no longer points the app at a hand-made
Whisper file: the speech model is downloaded once by the wizard into `<models_dir>/whisper/`
(`SCOPEWISE_WHISPER_MODEL` remains an override for tests). `SCOPEWISE_LLM_MODEL` still seeds the
selected model but a model is only "ready" once it has passed the check.

**What was and was not verified.** Unit tests use a fake engine, a local range-capable HTTP server
and a scripted compatibility check (interruptions of both downloads, resume, pause, restart, wrong
checksum, short disk, cloud models, model management). `make test-setup` uses the real Ollama: a
proxy cuts the connection mid-pull and the pull is resumed; a tiny model fails the real check and
the recommended one passes. A 39-check browser run used the real engines from a fresh state. Not
verified: a real Wi-Fi drop between Ollama and its registry (that failure arrives as an `error`
line, which is mapped from real message patterns but was not seen live), a drop during a real
Hugging Face download (tested against a local server plus one full real download), and the
bundled Ollama (desktop step).

## 2026-10-13: Desktop shell and packaging

**Shape.** Electron 44.7.1 with electron-builder 26.15.3, written in TypeScript and compiled to
CommonJS: a sandboxed preload has to be one self-contained CommonJS file that only requires
`electron`. The main process is small and split by job: `layout` (where things are), `env` (what each
child gets), `supervisor` (start, watch, stop), `pidfile`, `protocol` (serving the web app),
`security` (what a window may do). All but `main.ts` are plain functions or classes with unit tests
that run real child processes, not mocks.

**What the packaged app contains.** The Ollama standalone macOS archive (v0.35.1, pinned by SHA-256),
the api as one PyInstaller program, a `whisper-cli` built from a pinned whisper.cpp revision, and the
generated web app. whisper.cpp publishes no macOS binary, so `build-whisper.sh` builds it statically
(`BUILD_SHARED_LIBS=OFF`, Metal shader embedded, `GGML_NATIVE=OFF`, arm64, deployment target 13): one
7.7 MB file with only system libraries, which gave the same transcript at the same speed as the
development build. Sizes: `.dmg` 306 MB, installed app about 800 MB (Electron 287 MB, Ollama 455 MB,
api 30 MB, whisper-cli 8 MB).

**Ollama trimmed to what Apple Silicon loads.** The archive also holds Intel libraries, CPU backends
and a quantize tool; none are copied. `ollama`, `llama-server` and the two MLX Metal folders stay,
untouched, so Ollama's own signature stays valid. Both MLX folders stay because the newer one is built
for macOS 26.2 and the older (`mlx_metal_v3`) is what runs on macOS 14 to 26.1: dropping it would save
184 MB and break those Macs. Ollama's binaries need macOS 14, so that is the app's minimum. Ollama's own
MIT license is not in the archive, so the script fetches it from the same tag with its own checksum.

**The bundled Ollama is isolated.** It starts with a whitelisted environment (`PATH`, `TMPDIR`, `LANG`...
only): its own `HOME`, `OLLAMA_HOST=127.0.0.1:<port>`, `OLLAMA_MODELS` inside the app's data folder and
`OLLAMA_NO_CLOUD=1`. A user's own `OLLAMA_*` variables cannot reach it. Verified with the system Ollama
stopped (and a fresh data folder asking for models even when the system one has them).

**Lifecycle.** Two free ports are picked before anything starts; Ollama starts first and is waited for
on `/api/version`, then the api on `/health` (up to 90 s: the PyInstaller program unpacks itself, 4.5 s
warm and 6.7 s cold on this Mac). Each child leads its own process group, so stopping kills the group
(`SIGTERM`, then `SIGKILL` after 8 s) and nothing like `llama-server` or `whisper-cli` outlives it. A
crashed service is restarted once; a second crash shows a dialog with a button to the logs. Three more
guards: a pid file in the data folder lets the next start stop an Ollama left behind by a force quit
(only when the pid still runs the same program, so a recycled pid is never touched); the api watches the
app's pid (`SCOPEWISE_PARENT_PID`) and stops itself within two seconds when it is gone; a single-instance
lock avoids two apps fighting over one data folder. Closing the window quits the app: a transcription in
progress is then marked "interrupted" by the api's own recovery, and its audio is kept.

**PyInstaller `--onefile`.** The brief asks for a single executable. The cost is the unpack on every
start; `--onedir` would start faster but ship as a folder. Kept onefile; the few seconds hide behind a
"Starting Scopewise" page. electron-builder re-signs it ad hoc with everything else and it still runs
(checked on the installed copy, not only on the build output).

**Serving the web app: `app://scopewise`, not `file://`.** The generated pages use absolute asset
paths and the api needs an explicit CORS origin, which `file://` pages do not have. A privileged custom
scheme gives a normal origin without opening a port. `nuxt generate` writes no file for routes like
`/calls/<id>`, so a request without a file extension falls back to `200.html`; a missing asset stays a
404. Paths are resolved inside the web folder only (traversal, encoded `..` and NUL are refused).
Bug found by the tests: in the main process `new URL('app://x').origin` is `"null"` (Node, not
Chromium), so the app compares scheme and host.

**Security.** `contextIsolation` on, `nodeIntegration` off, `sandbox` on, devTools only when unpackaged,
and one value through `contextBridge` (`apiBase`, accepted only if it is `http://127.0.0.1:<port>`).
Every page is served with a CSP: `default-src 'none'`, scripts only from the app and by SHA-256 for the
two inline scripts Nuxt generates (import map and config), no `eval`, `connect-src` limited to the app
and its api. Requests to anything else are cancelled, permission requests are denied, `<webview>` is
blocked, navigation away from the app is blocked, and the only address opened in the user's browser is
`https://ollama.com` (the model library link). Electron fuses switched off: `runAsNode`, `NODE_OPTIONS`,
`--inspect`, plus `onlyLoadAppFromAsar`. Ollama is reachable only by the api: a test shows the page
cannot call it.

**"Not now".** In the packaged app it shows the page "Scopewise needs its models" with a Download button,
as in development; the app does not quit. The request returns on the next launch.

**Signing.** No Apple Developer ID, so the build is ad-hoc signed (`identity: "-"`,
`hardenedRuntime: false`; the electron-builder schema documents both and says hardened runtime breaks
Electron's frameworks under an ad-hoc signature). Apple Silicon will not run unsigned code at all, and
signing at all is what makes the app launch. Users still have to approve the first launch (README).

**Third-party notices.** One file at the repository root, shipped as a resource and rendered by the
`/notices` page (a build-time raw import, so the screen and the file cannot differ). Linked from every
page. Electron's license and Chromium's `LICENSES.chromium.html` are shipped next to it because
electron-builder does not include them. The route guard first redirected `/notices` to the setup screen,
so on a fresh install the licenses were unreachable; found by the first real run, fixed with a test.

**Nothing outside the repository.** Electron and electron-builder download their tools into
`.dev/electron-cache` and `.dev/electron-builder-cache`, not `~/Library/Caches`.

**What was verified, on this Mac (M2 Pro, macOS 27.0, installed copy of the `.dmg`'s app, system
Ollama stopped).** `make desktop-check`: 22 checks (both services up, loopback-only ports, CSP and
isolation, notices, a killed api restarted on its address, quit leaves no process behind, a force quit
leaves Ollama until the next start removes it and stops the api by itself). A 26-check run of the whole
product inside the app with real downloads: request screen, the speech model (574 MB) and a tiny model
through the bundled Ollama with progress, the tiny model refused by the check, Gemma 4 E4B accepted,
profile, upload, 5-minute call transcribed in 74 s, notes and proposal in 140 s, source quote, edit,
Markdown and PDF export, audio deleted, no connection beyond this computer, everything stopped on quit.
**Not verified:** opening the `.dmg` as a browser download (the quarantine flag and Gatekeeper's
approval; the copy was launched directly), installing into `/Applications` (outside the repository),
macOS 14 to 26.1 (this Mac loads the newer MLX libraries, so `mlx_metal_v3` has not run), Intel Macs
(not supported), the dialog after a second crash (the policy is unit-tested; the dialog was not seen),
and Electron's Save dialog for exports (the check saved downloads without it).
**gemma4:e4b was hard-linked** from the system Ollama's folder into the app's own for that run, to avoid
a 9.6 GB download; the download path itself was exercised with the tiny model and the speech model.

**App name and data folder (found while writing the README).** The first build had no `productName`, so
Electron named the app `scopewise-desktop`: the menu said "Quit scopewise-desktop" and data would have gone
to `~/Library/Application Support/scopewise-desktop`. `package.json` now sets `productName: "Scopewise"`, so
an installed app keeps everything in `~/Library/Application Support/Scopewise` (data, models, logs). Running
the shell from the repository uses `Scopewise (development)` instead, so a development shell never shares
models, data or the single-instance lock with an installed copy. Checked on the rebuilt `.dmg`'s app (launched
once, then the folder it created was removed again). Lesson: a test launch ignores a changed `HOME`, so
tests must always pass `--user-data-dir`.

