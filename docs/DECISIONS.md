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

**API config: only `POSTCALL_*` environment variables, via pydantic-settings.** Port, data
dir, models dir, Ollama URL and CORS origins have no defaults in code, so the app fails fast
instead of silently assuming a port or the default Ollama URL (the packaged binary must not
assume anything). The only default is the bind address, `127.0.0.1`. `make dev` supplies
dev values.

**One entrypoint for dev and packaged builds: `python -m app`.** It reads the same settings
and runs uvicorn on `settings.host:settings.port`, so PyInstaller can wrap the same module.

**CORS is configurable, not open.** The Nuxt dev server (`localhost:3000`) calls the api on
another port, so the allowed origins come from `POSTCALL_CORS_ORIGINS`. The desktop shell
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
explicitly, and the port is only a dev default (`POSTCALL_PORT`); the packaged app picks a
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
whisper.cpp uses 4 threads by default (`POSTCALL_WHISPER_THREADS`).

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

**Whisper paths are plain optional env vars for now** (`POSTCALL_WHISPER_CLI`,
`POSTCALL_WHISPER_MODEL`). The api starts without them and a job fails with "engine/model
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
(`llm_model`). `POSTCALL_LLM_MODEL` only seeds it when it is empty; the code reads the tag from
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

**Prompts** are `api/prompts/notes_v3.md` and `proposal_v2.md`, mention no model, and are found
next to the `app` package (override: `POSTCALL_PROMPTS_DIR`), so the packaged binary must bundle
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
(`POSTCALL_WHISPER_MODEL` remains an override for tests). `POSTCALL_LLM_MODEL` still seeds the
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
app's pid (`POSTCALL_PARENT_PID`) and stops itself within two seconds when it is gone; a single-instance
lock avoids two apps fighting over one data folder. Closing the window quits the app: a transcription in
progress is then marked "interrupted" by the api's own recovery, and its audio is kept.

**PyInstaller `--onefile`.** The brief asks for a single executable. The cost is the unpack on every
start; `--onedir` would start faster but ship as a folder. Kept onefile; the few seconds hide behind a
"Starting PostCall" page. electron-builder re-signs it ad hoc with everything else and it still runs
(checked on the installed copy, not only on the build output).

**Serving the web app: `app://postcall`, not `file://`.** The generated pages use absolute asset
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

**"Not now".** In the packaged app it shows the page "PostCall needs its models" with a Download button,
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
Electron named the app `postcall-desktop`: the menu said "Quit postcall-desktop" and data would have gone
to `~/Library/Application Support/postcall-desktop`. `package.json` now sets `productName: "PostCall"`, so
an installed app keeps everything in `~/Library/Application Support/PostCall` (data, models, logs). Running
the shell from the repository uses `PostCall (development)` instead, so a development shell never shares
models, data or the single-instance lock with an installed copy. Checked on the rebuilt `.dmg`'s app (launched
once, then the folder it created was removed again). Lesson: a test launch ignores a changed `HOME`, so
tests must always pass `--user-data-dir`.

## 2026-10-13: License and README

**License: MIT with a Beerware thank-you.** The repository had no license; the "MIT" in `desktop/package.json`
was my own assumption from the previous step, so it was replaced with `SEE LICENSE IN LICENSE` (npm's form for
a non-SPDX license) once the choice was made. "MIT + Beerware" can mean "either license" or "both"; I read it
as both: the MIT License governs, and the Beerware line ("if we meet some day... buy me a beer") is a stated
thank-you, not a condition. That keeps it a standard permissive license that companies can accept. The
models and engines keep their own licenses, listed in `THIRD_PARTY_NOTICES.md`.

**Screenshots come from the installed, packaged app,** not the development server: the dev server draws a
Nuxt devtools badge on every screen. `desktop/scripts/screenshots.mjs` drives the app over the DevTools
protocol using the data folder left by the end-to-end run (a finished draft, the settings with two models),
so the pictures are real output, not mock-ups. The wizard pictures are from that run's first launch.

**Numbers in the README are BENCHMARKS.md's,** with their caveats copied next to them (one sample, one run,
a draft key-facts file, scores assigned by Claude). Two additions from this step. The bundled `whisper-cli`
run on its own took 21.5 s and 17.0 s for the 5-minute sample, matching the 17.7 s measured in the spike, so
packaging did not slow it down. The 74 s seen inside the packaged app happened on a busy Mac (load average
about 10, Gemma resident, under 2 GB of free memory); the README says so instead of quoting only the best case.

**Hardware.** The 8 GB minimum is the figure the app shows for the default model (the model's 4.6 GB plus
speech, the app and macOS); it was never run on an 8 GB Mac and the README says so. macOS 14 is Ollama's own
minimum; only macOS 27 has been tried.

**Install instructions follow Apple's page** ("Safely open apps on your Mac"): try to open, then System
Settings, Privacy & Security, Open Anyway, confirm. That page does not mention Control-click and gives no time
limit, so neither is claimed. `xattr -dr com.apple.quarantine` is offered as a Terminal alternative and labelled
as a common workaround, not an Apple instruction. It has not been tried on a browser-downloaded copy.

**The sample's "menú de facturación".** Checking the transcript while writing the README showed that this
scope item is not an invention: the client asked for an automatic invoicing system (2:17) and the
interviewer's recap says "un menú de facturación" (2:52), so the draft lists both. The README uses it as the
example of why the source links and the editor exist.

## 2026-10-13: The app is called PostCall, package id mx.dev1.postcall

**Name.** The app was called "Scopewise" as a working title; it is now **PostCall**. It was renamed in one
change, everywhere, so nothing is half-renamed: the visible text, `PostCall.app` and `PostCall-1.0.0-arm64.dmg`,
the packages (`postcall-desktop`, `postcall-api`, `postcall-spike`), the packaged api program and its PyInstaller
spec, the environment variable prefix (`SCOPEWISE_*` is now `POSTCALL_*`), the internal address
(`app://postcall`), the api's title and log names, the SQLite file (`postcall.db`) and the data folder
(`~/Library/Application Support/PostCall`). The older entries in this log were renamed too, so their text
matches the code; the old name appears only in this paragraph.

**Package id: `mx.dev1.postcall`.** This is the `appId` in `electron-builder.yml`, which becomes the macOS
bundle identifier (`CFBundleIdentifier`). It is the reverse of the dev1.mx domain. Treat it as permanent:
changing it later makes macOS see a different app (separate permissions and data), and a Mac App Store
record is tied to its bundle id for good.

**What was not migrated, on purpose.** Nothing was ever released or installed under the old name (no
installed copy, no data folder in the real Library), so there is no migration code. The only leftover is an
empty development database, `.dev/data/scopewise.db`. Anyone with a `.env` that uses `SCOPEWISE_*` must
rename the variables: the api no longer reads them, so it stops at start with a "port field required" error
instead of silently using a wrong setting. `.env.example` has the new names.

**Two follow-ups from the rename.** `make build-api` now clears `desktop/build/api` first, because
electron-builder copies that whole folder and would otherwise have shipped the stale `scopewise-api`
program next to the new one. The README screenshots still show the old name; they are retaken in the next
change, together with the layout work, so they are taken once from the final screens. The GitHub repository
is still called `hacktoberfest-week3` (renaming it is the owner's call; the README links use that name).

## 2026-10-13: Responsive layout

**The problem, measured.** The report was "blank spaces". Opening the installed app at seven window sizes
(`desktop/scripts/layout-check.mjs`) showed it: every page lived in a fixed 760 px column, so the default
1200 px window used 63% of its width, a 1512 px screen 50% and a 2560 px one 30%. Short pages also left the
footer floating mid-window with up to 1000 px of empty space below it. Nothing scrolled sideways.

**What changed.** The page shell is wider (up to 1400 px, with padding that scales) and fills the window's
height, so the footer sits at the bottom. Two columns appear where there is something for the second column
and fold into one by themselves when there is not enough room (a CSS grid with `auto-fit`, so there are no
breakpoints to keep in step): Settings, the profile form, and the first-launch request, whose "Download now"
button now fits in the default window without scrolling. On the call page the transcript becomes a panel beside
the proposal from 1100 px up (a media query read by `useWideScreen`), so "Show in transcript" has somewhere
visible to land; below that it is the collapsible section it was. Home shows call cards (with language and
length) in a grid. Pages that are one short column of text or one form (upload, notices, the setup progress)
stay a centred 760 px column, because very long lines are harder to read than margins. Running text is capped
at 75 characters wherever it is.

**The check is part of the repository.** `layout-check.mjs` opens every page at 900x600, 1200x800, 1512x982,
1920x1080, 2560x1440, 600x800 and 390x844 in the real packaged app and fails on: sideways scrolling, more
than 40 px under the footer, a wide page using less than 85% of the window (or 1300 px), a single column that
is not centred or is over 760 px, two columns that are missing with room or present without it, and the
transcript panel missing or taller than the window. 42 combinations pass, and 7 more on a fresh install for
the first-launch request. Two of my own first rules were wrong and were corrected: the 32 px under the footer
is the page's own padding, and a sticky panel is judged by its height, not by where it starts at the top.
The panel itself had a real flaw (border and padding added about 10 px to its height), fixed with
`box-sizing: border-box`.

**What it does not claim.** Ultra-wide screens still have margins (the shell stops at 1400 px: 52% used at
2560 px), and Home looks sparse with one call. The check measures space and overflow; it does not judge beauty,
which was done by looking at the pictures.

**Timing, with the idle Mac.** The end-to-end run on the renamed, re-laid-out app on a quiet Mac took 29 s to
transcribe the 5-minute call and 52 s for notes and proposal, against 74 s and 140 s in the earlier run on a
busy one. Same code, same models; the README gives both, as a range.

## 2026-10-13: Deployment guide for Linux, Windows and the Mac App Store

A plan, not a build: `docs/DEPLOYMENT.md`. Nothing for these platforms was built or run here (one Mac), so every
claim in it is labelled verified (read in a cited source or measured in this repository) or unverified. Reading the
code against the documentation found problems worth knowing before any port starts:

- **Windows would break the app, not just fail to run it.** The API watches the desktop app with `os.kill(pid, 0)`.
  Python's docs say that on Windows any signal other than the two console events "will cause the process to be
  unconditionally killed by the TerminateProcess API", so the API would terminate the desktop app every two seconds.
  The same docs and Node's explain two other POSIX assumptions: `SIGTERM` is abrupt on Windows (there is no
  graceful stop then force sequence), and `os.sysconf` is Unix-only (the memory check on the model screen).
- **The audio decoder is macOS-only** (`afconvert`); Linux and Windows need a bundled decoder.
- **Ollama's Linux and Windows archives are about 1.4 GB** (the macOS one is 152 MiB), mostly GPU libraries, so the
  installers become about 1.6 to 1.7 GB unless the GPU libraries are trimmed or downloaded after install.
- **The Mac App Store conflicts with three design choices:** models downloaded after install (rule 2.4.5(iv)), a
  PyInstaller `--onefile` API that runs code unpacked outside the bundle (rule 2.5.2), and license keys (rule 2.4.5(vi),
  which also rules out the one-time-license idea in the store). The guide recommends prototyping the sandbox
  unknowns with a development-signed build before paying for anything.
- **Ubuntu 24.04 restricts the Chromium sandbox** through AppArmor, so a Linux `.deb` should ship an AppArmor profile;
  `--no-sandbox` is not an option because the window must stay sandboxed.
- **Signing options are version-dependent:** electron-builder 26.15.3 (used here) has `win.signtoolOptions` and
  `win.azureSignOptions`; version 27 replaces both with `win.sign`.

The effort figures in the guide's summary are my estimates, labelled as such, and the open decisions (platforms and
order, certificates, GPU libraries, a store edition with bundled models, updates) are listed for the owner.

## 2026-10-13: Eleven languages for the interface and for proposals

**Scope.** English, Spanish, French, Portuguese, Japanese, German, Russian, Italian, Hindi, Chinese
(Simplified) and Arabic, for three things that are separate: the interface, the proposal's language, and the few
strings the desktop shell shows before the interface loads.

**Library and shape.** Plain `vue-i18n` 11 through one Nuxt plugin, not the `@nuxtjs/i18n` module: the app is a
single-page app loaded from `app://`, so there is no URL per language to route, prerender or translate. English is
always loaded (it is the fallback), the other ten load when chosen. The language is the system's on first launch
(`navigator.languages`, matched by main part: `pt-BR` is Portuguese, `zh-TW` is the one Chinese we have, anything
else English), changed with a list in the header and remembered in `localStorage`, which survives restarts in the
packaged app. Verified in the real app under seven system languages, and a picked language wins over the system's
after a restart.

**No plural forms, on purpose.** Russian has three plural forms and Arabic six; instead of writing rules for them,
no message depends on a count. Sizes, speeds, durations and times are produced by `Intl` (a "gigabyte" unit, a
"minute" unit), which also writes them the way each language does. Messages around them take the finished text as a
value, and the translators were told to keep the grammar correct whatever it holds.

**Right to left.** Arabic sets `<html dir="rtl">`; the CSS uses logical properties (`margin-inline-start`...),
the play marker flips, and every piece of text that comes from a call or a proposal has `dir="auto"`, so a Spanish
proposal reads left to right inside an Arabic window. Found by running it: the header (brand, three pages, language
list) was wider than a phone-width window and, in right-to-left, overflowed off the left edge where nothing can
scroll to it, which my sideways-scroll check could not see. The header now wraps, and the check looks for content
past either edge.

**API errors by code.** Every refusal is now `ApiError(status, code, **values)`, answered as `{detail, code,
params}`; `detail` stays the English text, so nothing that read it breaks. The web app translates by `code`
(`apiErrors.<code>`) with the values filled in, shows the API's English text for a code it does not know, and the
same rule covers failed jobs (`error_code`). A test scans the source for every code raised and requires its English
message, and another requires the web app to have a message for each. Model descriptions are translated by model
name, and a test requires the English file to equal the API catalogue's text, so the two cannot drift.

**The translations.** Written by ten parallel AI translators from the English file, with these rules: keep
placeholders and product names, no `|` or `@` (vue-i18n syntax), and use exactly the section names the API already
uses in proposals for that language, so the interface and a generated proposal call things the same. Tests require
every language to have every key with the same values to fill in. **No native speaker has reviewed them**; the
README says so and tells people how to correct a file. The translators' own doubts (for example whether to call an
assumption "Hypothèse" or "Suposición", or "Spracherkennungsmodell" against "Sprachmodell", which already means the
language model) were read and left as written.

**Proposal languages are now all eleven**, the fixed wording (titles, the price sentence, the budget and deadline
questions) in `api/app/i18n.py` for the five new ones written by hand. The PDF export's built-in font draws Western
European text only, so for Japanese, Chinese, Russian, Hindi and Arabic proposals the PDF button is switched off with
a note and Markdown is the way out. Embedding fonts (and, for Arabic, text shaping) is left out on purpose.

**A real defect, found by trying the real model.** `gemma4:e4b` on the sample call, once per new language: Japanese,
Chinese, Russian and Hindi came out in their language (86 to 97% of the letters in the right script, every item
sourced or flagged). **Arabic did not: the section titles were Arabic but the whole body was Spanish** (0% Arabic
script): the model copied the notes' language. The prompt asked for the language once, at the top. `proposal_v2.md`
says it again at the end, says the notes may be in another language, and the API passes the language's own name too
("Arabic (العربية)"). Rerun: Arabic 100%, Japanese 90%, Spanish unchanged. The opt-in `make test-llm` now has a
test per script (Arabic, Japanese, Russian) so a later prompt edit cannot bring it back; it took two attempts
because my first Japanese check counted only ideographs and ignored hiragana and katakana.

**The check that did not check.** The first version of the leftover-English detector in `layout-check.mjs` reported
"all pass" and could not fail: its regular expressions sat inside a JavaScript template literal, where `\b` becomes
a backspace and `\s` becomes the letter `s`. Pointing it at English pages (where it must find plenty) exposed it;
the matching moved out into Node. Lesson in the desktop rules.

**What was checked, and how.** 95 web tests (every language has every message, no template contains raw text, every
key the code uses exists, every API error code and model note is covered), 49 desktop tests, API tests for the codes
and the wording. In the packaged app: 222 page and window combinations across all eleven languages (page language and
direction, layout, no content off either edge, no leftover English on the non-Latin languages), the first-launch
screen in all eleven on a fresh install, the language list used for real, and the system-language defaults. I looked
at the Arabic, Japanese and German screens.

**What was not.** The full upload-to-export flow was not repeated in each language (the code path is the same; only
the words differ). No native-speaker review. Chinese is Simplified only, so a Traditional-Chinese reader gets
Simplified. License texts, model and engine names, and API messages for a code the app has no translation for stay
in English. Third-party licenses are legal text: the page says in each language that they are in English.

**Timing, an environment note.** During this work the real-model tests ran on a Mac with a load average of 20 to
29: three Vitest workers from an unrelated project at about 70% CPU each for hours, and a busy Docker VM. The
Spanish test's 180 s timing assertion passed warm (104 s), and failed once at 207 s with every accuracy assertion
before it passing. It was left as it is, not loosened.

## 2026-10-13: Release 1.0.0

**What is released.** `PostCall-1.0.0-arm64.dmg`, 306,493,098 bytes, SHA-256
`306d0156d2f8f64eb50838ca71d7e9d1792e494071a2539d68e3b3e3d2f7cb69`, built with `make desktop-dist` from the
`release/1.0.0` branch (commit `77a19f6`; the only change on that branch is the api version, 0.1.0 to 1.0.0). Ad-hoc
signed, bundle id `mx.dev1.postcall`. Flow: `release/1.0.0` from `develop`, a pull request into `master`, the tag
`v1.0.0` on the merge commit, `master` merged back into `develop` through a pull request, then the GitHub Release.

**What was checked on this build, installed into a scratch folder.**
- Lifecycle (`shell-check.mjs`, 22 checks): 21 pass. The one failure, "a deep link that is not a pre-rendered page
  still loads the app", is a race in the script: it reads the page text in the first instant after navigating, when the
  body is still empty. A direct probe loaded the same deep link, waited for it to render (807 ms on this Mac) and found
  the page present, redirected to the setup screen as it should be.
- End to end with my system Ollama stopped (`full-flow.mjs`, 26 checks): **25 pass in the second complete run.** The
  failure is the speed target: notes and proposal took 194 s against the 3-minute target on a Mac whose load average
  was above 20 (earlier runs of the same step: 52 s on a quiet Mac, 104 s and 140 s on busy ones). Nothing was
  loosened. The run used a copy of the script with waits tripled for the loaded machine.
- **A first complete run failed at the edit step and I could not explain it.** The Save button stayed disabled
  after the script set the summary text, although real typing then enabled it and saved correctly. It did not
  recur: the same sequence was repeated 12 more times in the packaged app (immediately after opening the editor, with a
  delay, with a fuller input event, eight times in one session) and a second complete run passed that step. My best
  guess is that the scripted, instantaneous input event landed while the page was re-rendering; I did not prove it.
  If a freelancer reports edits that do not register, this is where to look.
- In the same code before the version bump: the 222 page-and-window combinations in all eleven languages, the first
  launch screen in all eleven, the language list, and 13 system-language checks (see the languages entry).
- Tests: api 217 (+7 opt-in), web 95, desktop 49; lint and typecheck clean.

**Not verified.** Opening the `.dmg` as a browser download through Gatekeeper's approval (the copy was launched
directly); installing into `/Applications`; macOS 14 to 26.1 (only macOS 27 was available); an 8 GB Mac; any real
freelancer using it (planned for the day after the release); native-speaker review of the translations.

**Follow-ups after 1.0.0, none of them blocking.** Fix the deep-link race in `shell-check.mjs` (wait for the page to
render). Update `full-flow.mjs`: it looked for curly quote characters in the source quote's text, but the quote is now
drawn with `<q>` so the marks are CSS, not text. Decide what to do about the unexplained edit-step failure above.


## 2026-10-14: The audio converter is no longer macOS-only (first step towards Linux packages)

Until now the only way to turn an mp3, m4a, wav or mp4 into the 16 kHz mono WAV that whisper.cpp reads was macOS's
`afconvert`. A Linux package needs something that runs there, and the decoder is the one place the api still assumed
macOS.

**FFmpeg, run as a separate program.** `FfmpegDecoder` runs `ffmpeg -nostdin -hide_banner -loglevel error -y -i SRC
-map 0:a:0 -ac 1 -ar 16000 -c:a pcm_s16le -f wav DEST`. `-nostdin` keeps it from waiting for a key inside a background
job, and `-map 0:a:0` takes the first audio stream, so the video track of an mp4 is ignored and a file with no audio
fails instead of producing silence. A file FFmpeg rejects becomes `decode_failed`; a missing program becomes
`decoder_missing`, the same two codes `afconvert` already used, so the web app needs no new message.

**Why a separate program and not a Python library.** PyAV would have kept everything in one process, but its wheels
bundle FFmpeg built with libx264 and libx265, which are GPL: shipping them inside a package would change the licence of
what we distribute. A separate FFmpeg binary, built by us with only the LGPL parts we need (decoders for mp3, aac and
PCM; the mp3, mov and wav demuxers; the wav muxer), keeps PostCall's MIT terms and keeps the source offer simple. That
build comes with the Linux packaging step; this step only teaches the api to use whatever FFmpeg it is pointed at.

**Which decoder is used.** `default_decoder(ffmpeg)`: an explicit `POSTCALL_FFMPEG` path always wins (the Linux desktop
app sets it to the FFmpeg it ships); otherwise macOS keeps `afconvert` (nothing changes for the macOS app, which has no
FFmpeg), and anything else, or a Mac where `afconvert` is somehow missing, looks for `ffmpeg` on the PATH.

**The message** for `decoder_missing` said "The macOS audio converter is missing". It now says "The audio converter is
missing" in all eleven languages, since it can be either program.

**Tests.** The command each decoder builds and the two failure mappings are tested with `subprocess.run` replaced (no
program needed), and so is the choice of decoder. Three-second clips of the sample call (mp3, m4a, mp4, wav at 8 kHz
stereo, to force the downmix and resample) in `api/tests/data/` run through the real program wherever it exists:
`afconvert` here, FFmpeg in a Debian container (FFmpeg 7.1.5 from apt: it checks our command line, not the LGPL build,
which is tested with the packages). All four formats come out as 16 kHz mono 16-bit WAV of the right length, and a file
that is not audio is refused. Not covered: an mp4 that really has a video track (no way to make one without FFmpeg on
this Mac).

## 2026-10-14: No hosted server mode for Windows users

Asked whether Windows users, who have no PostCall version yet, should be served from a dedicated Linux server. No.
A shared server moves clients' confidential calls off the user's computer, which is the thing the product exists to
avoid; the api and the app are written for one person on one machine (loopback only, no accounts, no encryption), so a
server mode would be a second product; and the Windows api and transcription programs have to be built on Windows
either way. The plan stays a native Windows version, with the Linux package under WSL2 as an untested stopgap for
technical users and a self-hosted team mode only if asked for, as an explicit opt-in. Reasoning in
[DEPLOYMENT.md](DEPLOYMENT.md) section 5.4.
