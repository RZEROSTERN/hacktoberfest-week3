"""Transcription benchmark: whisper.cpp (whisper-cli) vs faster-whisper.

Usage:
  uv run python bench_whisper.py cpp  <model.bin> <audio.wav> <label> [threads] [extra whisper-cli flags]
  uv run python bench_whisper.py fw   <model_name> <audio>     <label> [threads]

Appends one JSON line per run to $SPIKE_OUT/whisper_results.jsonl and saves the transcript as
$SPIKE_OUT/<label>.json (segments with start/end seconds and text).
"""

import json
import os
import re
import resource
import subprocess
import sys
import time
import wave
from pathlib import Path

OUT = Path(os.environ["SPIKE_OUT"])
WHISPER_CLI = Path(os.environ.get("WHISPER_CLI", "whisper-cli"))  # only used by the cpp engine


def audio_seconds(path: str) -> float:
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def run_cpp(model: str, audio: str, label: str, threads: int, extra: list[str]) -> dict:
    prefix = OUT / label
    cmd = [
        "/usr/bin/time", "-l",
        str(WHISPER_CLI), "-m", model, "-f", audio, "-l", "auto",
        "-t", str(threads), "-oj", "-of", str(prefix), *extra,
    ]  # fmt: skip
    start = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    wall = time.perf_counter() - start
    peak = int(re.search(r"(\d+)\s+maximum resident set size", proc.stderr).group(1))
    data = json.loads(Path(f"{prefix}.json").read_text())
    segments = [
        {"start": s["offsets"]["from"] / 1000, "end": s["offsets"]["to"] / 1000, "text": s["text"].strip()}
        for s in data["transcription"]
    ]
    language = data["result"]["language"]
    return {"wall": wall, "peak_rss_bytes": peak, "segments": segments, "language": language}


def run_fw(model_name: str, audio: str, label: str, threads: int, extra: list[str]) -> dict:
    from faster_whisper import WhisperModel

    t0 = time.perf_counter()
    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=threads)
    load = time.perf_counter() - t0
    start = time.perf_counter()
    gen, info = model.transcribe(audio, beam_size=5)  # language=None -> auto-detect
    segments = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in gen]
    wall = time.perf_counter() - start
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # bytes on macOS
    return {
        "wall": wall, "load": load, "peak_rss_bytes": peak, "segments": segments,
        "language": info.language,
    }  # fmt: skip


def main() -> None:
    engine, model, audio, label = sys.argv[1:5]
    threads = int(sys.argv[5]) if len(sys.argv) > 5 else 8
    duration = audio_seconds(audio) if audio.endswith(".wav") else float("nan")
    extra = sys.argv[6:]
    result = (run_cpp if engine == "cpp" else run_fw)(model, audio, label, threads, extra)
    segments = result.pop("segments")
    (OUT / f"{label}.json").write_text(json.dumps(segments, ensure_ascii=False, indent=1))
    row = {
        "label": label, "engine": engine, "model": Path(model).name, "audio": Path(audio).name,
        "audio_seconds": round(duration, 1), "threads": threads, "extra_flags": extra,
        "wall_seconds": round(result.pop("wall"), 1),
        "peak_rss_mb": round(result.pop("peak_rss_bytes") / 1e6),
        **result,
    }  # fmt: skip
    row["realtime_factor"] = round(row["wall_seconds"] / duration, 3)
    row["segments"] = len(segments)
    with (OUT / "whisper_results.jsonl").open("a") as f:
        f.write(json.dumps(row) + "\n")
    print(json.dumps(row, indent=1))


if __name__ == "__main__":
    main()
