import threading
import time
import wave
from collections.abc import Callable
from pathlib import Path

from app.audio import TranscriptionError
from app.errors import Cancelled
from app.transcribe import TranscribedSegment, TranscriptResult

SEGMENTS = [
    TranscribedSegment(0.0, 3.5, "Hola, gracias por recibirme."),
    TranscribedSegment(3.5, 9.0, "Necesitamos un sistema para reservaciones."),
]


class FakeDecoder:
    def to_wav(self, source: Path, dest: Path) -> None:
        with wave.open(str(dest), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 16000)  # one second of silence


class FakeTranscriber:
    """Canned transcriber. `gate` blocks it until the test releases it (or the job is cancelled)."""

    def __init__(self) -> None:
        self.gate: threading.Event | None = None
        self.fail_with: str | None = None
        self.progress_steps: list[float] = []
        self.calls = 0

    def transcribe(
        self,
        wav: Path,
        work_dir: Path,
        on_progress: Callable[[float], None],
        cancel: threading.Event,
    ) -> TranscriptResult:
        self.calls += 1
        for step in self.progress_steps:
            on_progress(step)
        if self.gate is not None:
            while not self.gate.wait(timeout=0.05):
                if cancel.is_set():
                    raise Cancelled
        if self.fail_with:
            raise TranscriptionError(self.fail_with)
        return TranscriptResult(language="es", segments=list(SEGMENTS))


def wait_until(predicate: Callable[[], bool], timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not reached in time")
