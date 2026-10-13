# Model spike

Scripts used to pick the transcription engine and the language model. Results and the
reasoning are in [docs/BENCHMARKS.md](../docs/BENCHMARKS.md) and
[docs/DECISIONS.md](../docs/DECISIONS.md). This folder is not shipped in the app and the api
must not import from it.

| Path | What it is |
| --- | --- |
| `bench_whisper.py` | Runs whisper.cpp (`whisper-cli`) or faster-whisper on a file and records time, peak memory, language and segments. |
| `bench_llm.py` | Chunked notes extraction + proposal drafting through Ollama, with the code checks (segment ids, sources, prices in the profile, forbidden extras). `--no-quote` is prompt v2. |
| `wer.py` | Word disagreement between two transcripts (not a real error rate: there is no human reference yet). |
| `show.py` | Prints the notes and proposal of a result file for reading. |
| `prompts/` | `notes_v1.md`, `notes_v2.md`, `proposal_v0.md`: experiment prompts. |
| `profile.json` | Fake freelancer profile used to draft proposals. |
| `results/` | Transcripts, per-run LLM outputs and `manual_scoring.json` (how each key fact was scored). |

The environment is a separate uv project (faster-whisper, onnxruntime, PyAV, cmake) so the
api does not inherit those dependencies. It ran on Python 3.14; the api itself is pinned to 3.12.

Large things live in the git-ignored `.dev/` folder: the whisper.cpp checkout and build, the
Whisper models, converted audio.

```sh
cd spike && uv sync
git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git ../.dev/whisper.cpp
.venv/bin/cmake -S ../.dev/whisper.cpp -B ../.dev/whisper.cpp/build
.venv/bin/cmake --build ../.dev/whisper.cpp/build -j --config Release
sh ../.dev/whisper.cpp/models/download-ggml-model.sh large-v3-turbo-q5_0 ../.dev/models/whisper.cpp
afconvert -f WAVE -d LEI16@16000 -c 1 ../samples/interview.mp3 ../.dev/audio/interview.wav
```
