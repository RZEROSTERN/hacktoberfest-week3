import subprocess
import wave
from pathlib import Path
from typing import Protocol

SUPPORTED_EXTENSIONS = (".mp3", ".m4a", ".wav", ".mp4")


class TranscriptionError(Exception):
    """A failure with a stable `code` the UI turns into a plain-language message."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Decoder(Protocol):
    def to_wav(self, source: Path, dest: Path) -> None:
        """Write `source` as 16 kHz mono 16-bit WAV to `dest`."""
        ...


class AfconvertDecoder:
    """Uses the `afconvert` tool that ships with macOS (mp3, m4a, wav and mp4 audio)."""

    def to_wav(self, source: Path, dest: Path) -> None:
        cmd = ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(source), str(dest)]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except FileNotFoundError as exc:
            raise TranscriptionError("decoder_missing") from exc
        except subprocess.CalledProcessError as exc:
            raise TranscriptionError("decode_failed") from exc


def wav_duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return float(w.getnframes() / w.getframerate())
