import shutil
import subprocess
import sys
import wave
from pathlib import Path
from typing import Protocol

from app.proc import NO_WINDOW

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
            subprocess.run(cmd, check=True, capture_output=True, creationflags=NO_WINDOW)
        except FileNotFoundError as exc:
            raise TranscriptionError("decoder_missing") from exc
        except subprocess.CalledProcessError as exc:
            raise TranscriptionError("decode_failed") from exc


class FfmpegDecoder:
    """Uses FFmpeg, run as a separate program (mp3, m4a, wav and mp4 audio).

    Where macOS's `afconvert` is not available (Linux), the desktop app bundles a small FFmpeg and
    tells the api where it is. In development any `ffmpeg` on the PATH works.
    """

    def __init__(self, program: str | Path = "ffmpeg") -> None:
        self.program = str(program)

    def to_wav(self, source: Path, dest: Path) -> None:
        cmd = [
            self.program,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:a:0",  # the first audio stream; a video track is ignored, no audio is an error
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            str(dest),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, creationflags=NO_WINDOW)
        except FileNotFoundError as exc:
            raise TranscriptionError("decoder_missing") from exc
        except subprocess.CalledProcessError as exc:
            raise TranscriptionError("decode_failed") from exc


def default_decoder(ffmpeg: Path | None = None) -> Decoder:
    """An explicit FFmpeg wins; otherwise macOS uses its own converter, anything else FFmpeg."""
    if ffmpeg is not None:
        return FfmpegDecoder(ffmpeg)
    if sys.platform == "darwin" and shutil.which("afconvert") is not None:
        return AfconvertDecoder()
    return FfmpegDecoder()


def wav_duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return float(w.getnframes() / w.getframerate())
