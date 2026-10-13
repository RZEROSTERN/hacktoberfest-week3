# Benchmarks

Model spike run on 2026-10-13. Raw outputs and scripts are in [spike/](../spike/); how
each fact was scored is in [spike/results/manual_scoring.json](../spike/results/manual_scoring.json).

**Machine:** MacBook, Apple M2 Pro, 16 GB RAM, macOS 27.0, Ollama 0.35.1 (native, Metal),
whisper.cpp built from commit `0c7be69` (Metal + Accelerate), faster-whisper 1.2.1 with
CTranslate2 4.8.3 and PyAV 16.1.0.

**Test material:** `samples/interview.mp3`, a 5 min 24 s Spanish role-play of a pizzeria
owner asking for a website. The 32-minute file used for the speed targets is that recording
repeated six times (there is no longer recording yet), so it measures speed but not quality.

## Results against the targets

| Target | Result |
| --- | --- |
| 30-minute call transcribed in under 10 minutes | **Met** by whisper.cpp: 88 s for 32 min of audio. faster-whisper `large-v3-turbo` needed 666 s (11.1 min) and misses it. |
| Notes + proposal in under 3 minutes | **Met** by `gemma4:e4b`: 64 s for the 5-minute call, 160 s for the 32-minute call (5 chunks). `qwen3.5:9b` takes 126 s and 322 s, so it misses at 30 minutes. |
| At least 90% of the expected key facts | **Met** by `gemma4:e4b` and `qwen3.5:9b`: 12 of 13 (92%). The other three models are below 70%. |
| Zero invented requirements or prices | **Met** by `gemma4:e4b` on the 5-minute call (0 invented items, no price outside the profile's rates). See the caveats: one wrong "out of scope" item appears in the 32-minute run. `qwen3.5:9b` added two small inventions. |

**Chosen combination: whisper.cpp with `large-v3-turbo` (q5_0) + `gemma4:e4b`.**
First-launch download: 547 MiB + 6.6 GB. The key facts file is still a draft that a person has
not confirmed (see [samples/README.md](../samples/README.md)), so the fact counts below are
provisional.

## Transcription

Sample is 323.9 s long. "RTF" is processing time divided by audio length (lower is faster).

| Engine | Model | Download | 5.4 min | 32.4 min | Peak memory |
| --- | --- | --- | --- | --- | --- |
| whisper.cpp (Metal) | `small` | 465 MiB | 14.0 s (RTF 0.043) | 48.7 s (0.025), degraded, see note 1 | 0.9 to 1.1 GB |
| whisper.cpp (Metal) | `large-v3-turbo` q5_0 | 547 MiB | 17.7 s (0.055) | 88.3 s (0.045), see note 1 | 0.9 to 1.1 GB |
| faster-whisper (CPU, int8) | `small` | about 0.5 GB, see note 2 | 64.3 s (0.199) | not run | 0.95 GB |
| faster-whisper (CPU, int8) | `large-v3-turbo` | about 1.5 GB, see note 2 | 106.7 s (0.329) | 666 s (0.343) | 1.4 to 1.7 GB |

All four detected Spanish automatically. Licenses: whisper.cpp is MIT; the Whisper models
(including `large-v3-turbo`) are MIT; faster-whisper is MIT.

1. **Long audio.** On the 32-minute file, whisper.cpp `large-v3-turbo` with its default
   settings fell apart after the first copy: 1,487 tiny fragments ("bueno", "y",
   "entonces") instead of about 240 segments, and `small` degraded in the last two copies.
   Passing `-mc 0` (do not condition on previous text) fixed it for turbo (388 segments,
   3,369 words, against 3,429 words from faster-whisper). This may partly be an artifact of
   six identical copies, but it shows a real risk. `-mc 0` has a cost: on the real sample the
   default run wrote "supermanzana 316" and "Bonfil", while `-mc 0` wrote "Supermanzada" and
   "Bofi". Plan for the transcription step: use the defaults, and re-run with `-mc 0` if the
   output looks degenerate (far too many short segments).
2. The two faster-whisper models together take 2.0 GB on disk; they were not measured
   separately.

**Word accuracy.** There is no human-checked transcript yet, so real word error rate is
unknown. What was measured is how much the transcripts disagree with each other (normalized
words, 5.4-minute sample):

| Pair | Disagreement |
| --- | --- |
| whisper.cpp turbo (`-mc 0`) vs faster-whisper turbo | 4.9% |
| whisper.cpp turbo (default) vs faster-whisper turbo | 6.2% |
| whisper.cpp turbo (default) vs whisper.cpp turbo (`-mc 0`) | 6.0% |
| whisper.cpp small vs faster-whisper small | 3.6% |
| any `small` vs any `turbo` | 6.7% to 9.5% |

`small` disagrees with the `turbo` runs more than they disagree with each other, which
suggests `turbo` is closer to the truth, but that is an inference. Visible errors: the city
is spelled "Kakún" or "Cacún" once and "Cancún" later; one phrase near 313 s ("Solo la misa
contiene") looks like a mishearing.

**Bundling.**

| | whisper.cpp | faster-whisper |
| --- | --- | --- |
| What ships | `whisper-cli` plus 6 dylibs, about 8 MB | Python packages, about 330 MB (ctranslate2, onnxruntime, PyAV with bundled FFmpeg, numpy) |
| Apple Silicon | Metal GPU, about 6x faster here | CPU only (the docs do not mention Apple Silicon; CTranslate2 lists ARM64 CPUs and NVIDIA GPUs) |
| Input | 16-bit WAV only; macOS `afconvert` converts mp3 in 0.6 s, no ffmpeg needed | Any format through PyAV |
| Fragility | Needs `-mc 0` fallback on long audio | 1.2.1 crashed with the latest PyAV (19); needs `av<17` |

whisper.cpp wins on speed, size and simplicity, so it is the engine.

## Language models

All five models are Apache 2.0 (read from `ollama show --license`). Notes are extracted per
8-minute chunk, then merged in code (exact-duplicate removal). Everything runs with
temperature 0, 8,192 tokens of context, `think: false`, and a JSON schema as the output
format. The test freelancer profile is in [spike/profile.json](../spike/profile.json).

Final pipeline (prompt v2: the model writes text and segment ids, not quotes):

| Model | Download | Resident memory | Notes | Proposal | 5-min call | 32-min call | Speed | Key facts | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `gemma4:e4b` | 6.6 GB | 4.6 GB | 40.0 s | 23.7 s | **63.8 s** | **160.2 s** | 44 tok/s | **12 / 13 (92%)** | Meets all targets. Default. |
| `qwen3.5:9b` | 6.6 GB | 6.3 GB | 71.3 s | 54.8 s | 126.2 s | 321.8 s | 22 tok/s | 12 / 13 (92%) | Too slow at 30 min; 2 small inventions. |
| `qwen3.5:4b` | 3.3 GB | 3.8 GB | 24.8 s | 17.1 s | 41.9 s | 175.2 s | 35 tok/s | 9 / 13 (69%) | Fast, but misses facts and invented an out-of-scope item. |
| `mistral-nemo:12b` | 7.1 GB | 7.6 GB | 49.1 s | 32.5 s | 81.7 s | not run | 17 tok/s | 8 / 13 (62%) | Thin notes. |
| `gemma4:12b` | 8.0 GB | about 9 GB, see note | 164.3 s | 74.2 s | 239.2 s | not run | 6 tok/s | 4.5 / 13 (35%) | Too slow and too terse on this Mac. |

"Resident memory" is the peak RSS of the Ollama runner process. For `gemma4:12b` the
runner's RSS was only 0.9 GB because the weights sit in Metal buffers; the Ollama log shows
a 7.0 GiB GPU model buffer plus 0.8 GiB on the CPU, so it needs roughly 9 GB in total.
The benchmark also logged system-wide memory growth, but it varied from 0.4 to 7 GB between
runs because other apps were changing memory at the same time, so it is not reported here.

What each model got wrong (details in `manual_scoring.json`):

- **`gemma4:e4b`**: no invented features. Misses the contact-info item (F12). Its open
  questions are weak: no budget question in either v2 run, and one is the freelancer's
  own line ("¿Qué partes quieres modificar?"). In the 32-minute run an out-of-scope item
  "Sección de clientes frecuentes" appears, a misreading of the client's answer when a chunk
  cuts it off from the question.
- **`qwen3.5:9b`**: writes "videos de preparación" (only "how we prepare the pizzas" was
  said) and a timeline "basado en la revisión de documentos" (no documents were mentioned).
  Best open questions of all (deadline, budget, whether photos and videos are ready).
- **`qwen3.5:4b`**: merges requirements into raw sentence fragments, misses the locations
  and the prototype timeline, and lists "Sección de recetas o procesos de preparación
  detallados" as out of scope, which nobody said.
- **`mistral-nemo:12b`**: with the first prompt it wrote its notes in English. Raises both
  budget and deadline as open questions. Scope has a single item.
- **`gemma4:12b`**: lumps menu, reservations, gallery and invoicing into one generic
  requirement. Prompt processing ran at 44 tok/s and constrained-JSON output at about 6
  tok/s. It also took 147 s to load cold and hung on its first attempts while the Mac was
  short on memory; it only completed once warm. It was not tried with thinking switched on.

**Key fact missed by every model:** F12 (contact information on the page, proposed by the
interviewer).

**Open questions are the weak spot of the default model.** In its 5-minute v2 run
`gemma4:e4b` asked about neither the budget nor the deadline (in the 32-minute run it asked
about the deadline only); every other model asked about both in its v2 runs. No proposal
used a client budget as a price, because the call never mentions one. This points to a
deterministic fix in code: when the notes hold no budget or deadline, always add those two
open questions.

### Prompt iterations

| Prompt | Change | `gemma4:e4b` | `qwen3.5:9b` | `mistral-nemo:12b` |
| --- | --- | --- | --- | --- |
| v1 | Items carry text, a word-for-word quote and segment ids; richer client context | 11.5 / 13, 103 s (5 min), 224 s (32 min) | 12 / 13, 172 s, 531 s | 9.5 / 13, 198 s |
| v2 | Quotes dropped: code looks them up from the cited segments | 12 / 13, 64 s, 160 s | 12 / 13, 126 s, 322 s | 8 / 13, 82 s |

Dropping the model-written quotes cut the output by roughly a third, made the app's
transcript excerpt correct by construction (only 38 of 53 and 60 of 73 model-written quotes
matched the transcript word for word in the v1 32-minute runs), and cut e4b time by 38%. A
first prompt (v0) was discarded: its single run overlapped with model downloads.

### Rules checked by code on every run

- Every segment id exists in the transcript: no bad ids in any v2 run (one bad id appeared
  in the v1 32-minute `gemma4:e4b` run).
- No scope item or deliverable lacks both a source and an assumption flag.
- Every number in the investment section appears in the freelancer's profile.
- The summary contains no price (the first check also flagged the address "316", a false
  positive that was ignored).
- Output validated with Pydantic: no run needed the retry.
- Keyword scan for features nobody mentioned (WhatsApp, payments, SEO, delivery, and so
  on): no hits in any run. Everything else was checked by reading.

## Caveats

- **One sample, one run per configuration.** The call has 13 key facts, so one fact is
  7.7 percentage points. Temperature 0 makes each run repeatable but not representative.
- **The key facts are a draft** written by Claude from a Whisper transcript. A person who
  heard the call needs to confirm them, and a human reference transcript is needed for a
  real word error rate. The scores here were also assigned by Claude, not by a person.
- **Timings were taken on a busy Mac** (browser, IDE, Android Studio, Docker, a Time Machine
  backup at one point, 11 to 53% free memory, 30+ GB of swap in use). They are probably worse
  than on a quiet machine. Cold model loads took 30 to 150 s.
- **The LLM runs used the `-mc 0` transcript**, which wrote "Supermanzada" and "Bofi".
- **No quality test on a real 30-minute call.** The 32-minute file repeats the same call.
- **Not tried:** quantizations other than the Ollama defaults, `gemma4:e2b`, Whisper
  Core ML, `think` on, other chunk sizes, or a model-based consolidation of merged notes.

## Reproduce

```sh
cd spike
export SPIKE_OUT=../.dev/out WHISPER_CLI=../.dev/whisper.cpp/build/bin/whisper-cli
uv run python bench_whisper.py cpp <ggml-model.bin> <audio.wav> <label> 8 -mc 0
SCOPEWISE_OLLAMA_URL=http://127.0.0.1:11434 \
  uv run python bench_llm.py gemma4:e4b <transcript.json> <label> --no-quote
```
