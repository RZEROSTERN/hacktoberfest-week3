import json
import re
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.audio import TranscriptionError
from app.errors import Cancelled

PROGRESS_RE = re.compile(r"progress =\s*(\d+)%")


@dataclass(frozen=True)
class TranscribedSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptResult:
    language: str
    segments: list[TranscribedSegment]


class Transcriber(Protocol):
    def transcribe(
        self,
        wav: Path,
        work_dir: Path,
        on_progress: Callable[[float], None],
        cancel: threading.Event,
    ) -> TranscriptResult:
        """Transcribe a 16 kHz mono WAV. `on_progress` takes 0 to 1. Raises Cancelled."""
        ...


def looks_degenerate(segments: list[TranscribedSegment]) -> bool:
    """Whisper sometimes falls into a flood of one- and two-word fragments on long audio.

    In the model spike the broken run had 69% such segments; healthy runs had 15% or less.
    """
    if len(segments) < 20:
        return False
    short = sum(1 for s in segments if len(s.text.split()) <= 2)
    return short / len(segments) > 0.4


class WhisperCppTranscriber:
    """Runs the whisper.cpp `whisper-cli` binary. Language is always auto-detected."""

    def __init__(
        self, cli: Path | None, model: Path | Callable[[], Path | None] | None, threads: int
    ) -> None:
        self._cli = cli
        # A fixed path, or a function that finds the model on each run (so later downloads count).
        self._model_source = model if callable(model) else (lambda: model)
        self._threads = threads

    def transcribe(
        self,
        wav: Path,
        work_dir: Path,
        on_progress: Callable[[float], None],
        cancel: threading.Event,
    ) -> TranscriptResult:
        if self._cli is None or not self._cli.is_file():
            raise TranscriptionError("engine_missing")
        model = self._model_source()
        if model is None or not model.is_file():
            raise TranscriptionError("model_missing")
        result = self._run(self._cli, model, wav, work_dir, on_progress, cancel, [])
        if looks_degenerate(result.segments):
            # `-mc 0` stops conditioning on previous text, which fixes the fragment flood.
            result = self._run(self._cli, model, wav, work_dir, on_progress, cancel, ["-mc", "0"])
        return result

    def _run(
        self,
        cli: Path,
        model: Path,
        wav: Path,
        work_dir: Path,
        on_progress: Callable[[float], None],
        cancel: threading.Event,
        extra: list[str],
    ) -> TranscriptResult:
        prefix = work_dir / "whisper"
        cmd = [
            str(cli), "-m", str(model), "-f", str(wav), "-l", "auto",
            "-t", str(self._threads), "-oj", "-of", str(prefix), "-pp", *extra,
        ]  # fmt: skip
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
            )
        except OSError as exc:
            raise TranscriptionError("engine_missing") from exc

        def read_progress() -> None:
            assert proc.stderr is not None
            for (
                line
            ) in proc.stderr:  # also drains stderr so the process never blocks on a full pipe
                match = PROGRESS_RE.search(line)
                if match:
                    on_progress(int(match.group(1)) / 100)

        reader = threading.Thread(target=read_progress, daemon=True)
        reader.start()
        try:
            while True:
                try:
                    proc.wait(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    if cancel.is_set():
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait()
                        raise Cancelled from None
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            reader.join(timeout=2)

        if proc.returncode != 0:
            raise TranscriptionError("transcribe_failed")
        return self._parse(prefix.with_suffix(".json"))

    @staticmethod
    def _parse(path: Path) -> TranscriptResult:
        try:
            data = json.loads(path.read_text())
            segments = [
                TranscribedSegment(
                    start=item["offsets"]["from"] / 1000,
                    end=item["offsets"]["to"] / 1000,
                    text=item["text"].strip(),
                )
                for item in data["transcription"]
                if item["text"].strip()
            ]
            return TranscriptResult(language=data["result"]["language"], segments=segments)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise TranscriptionError("transcribe_failed") from exc
