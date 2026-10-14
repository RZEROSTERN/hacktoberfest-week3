"""The audio decoders: the command each one builds, how failures are named, which one is chosen.

The real-converter tests run only where the program exists (afconvert on macOS, ffmpeg wherever
it is installed, which includes the Linux build container). They use three-second clips in
tests/data.
"""

import shutil
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any

import pytest

from app.audio import (
    AfconvertDecoder,
    Decoder,
    FfmpegDecoder,
    TranscriptionError,
    default_decoder,
    wav_duration,
)
from app.config import Settings

DATA = Path(__file__).parent / "data"
# clip-video.mp4 has a video track as well as the sound; the converters must take the sound only.
CLIPS = ["clip.mp3", "clip.m4a", "clip.wav", "clip.mp4", "clip-video.mp4"]


class Recorder:
    """Stands in for `subprocess.run`: remembers the command, optionally fails."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.commands: list[list[str]] = []

    def __call__(self, cmd: list[str], **kwargs: Any) -> None:
        self.commands.append(cmd)
        assert kwargs == {"check": True, "capture_output": True}
        if self.error is not None:
            raise self.error


def record(monkeypatch: pytest.MonkeyPatch, error: Exception | None = None) -> Recorder:
    recorder = Recorder(error)
    monkeypatch.setattr(subprocess, "run", recorder)
    return recorder


def test_ffmpeg_command_downmixes_to_16khz_mono_wav(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = record(monkeypatch)
    FfmpegDecoder("/opt/PostCall/ffmpeg").to_wav(Path("in.m4a"), Path("out.wav"))
    (cmd,) = recorder.commands
    assert cmd[0] == "/opt/PostCall/ffmpeg"
    assert cmd[-1] == "out.wav"
    assert cmd[cmd.index("-i") + 1] == "in.m4a"
    assert "-nostdin" in cmd  # never wait for a keypress inside a background job
    assert cmd[cmd.index("-map") + 1] == "0:a:0"  # a video track in an mp4 is ignored
    assert cmd[cmd.index("-ac") + 1] == "1"
    assert cmd[cmd.index("-ar") + 1] == "16000"
    assert cmd[cmd.index("-c:a") + 1] == "pcm_s16le"
    assert cmd[cmd.index("-f") + 1] == "wav"


def test_afconvert_command(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = record(monkeypatch)
    AfconvertDecoder().to_wav(Path("in.m4a"), Path("out.wav"))
    assert recorder.commands == [
        ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", "in.m4a", "out.wav"]
    ]


@pytest.mark.parametrize("decoder", [AfconvertDecoder(), FfmpegDecoder()])
def test_a_missing_program_is_decoder_missing(
    decoder: Decoder, monkeypatch: pytest.MonkeyPatch
) -> None:
    record(monkeypatch, FileNotFoundError("no such program"))
    with pytest.raises(TranscriptionError) as raised:
        decoder.to_wav(Path("in.mp3"), Path("out.wav"))
    assert raised.value.code == "decoder_missing"


@pytest.mark.parametrize("decoder", [AfconvertDecoder(), FfmpegDecoder()])
def test_a_file_the_program_rejects_is_decode_failed(
    decoder: Decoder, monkeypatch: pytest.MonkeyPatch
) -> None:
    record(monkeypatch, subprocess.CalledProcessError(1, "x", stderr=b"Invalid data found"))
    with pytest.raises(TranscriptionError) as raised:
        decoder.to_wav(Path("in.mp3"), Path("out.wav"))
    assert raised.value.code == "decode_failed"


def test_an_explicit_ffmpeg_wins_even_on_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/afconvert")
    decoder = default_decoder(Path("/opt/PostCall/ffmpeg"))
    assert isinstance(decoder, FfmpegDecoder)
    assert decoder.program == "/opt/PostCall/ffmpeg"


def test_macos_uses_its_own_converter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/afconvert")
    assert isinstance(default_decoder(), AfconvertDecoder)


def test_macos_without_afconvert_falls_back_to_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert isinstance(default_decoder(), FfmpegDecoder)


def test_linux_uses_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert isinstance(default_decoder(), FfmpegDecoder)


def test_the_ffmpeg_path_comes_from_the_environment(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert settings.ffmpeg is None
    monkeypatch.setenv("POSTCALL_FFMPEG", "/opt/PostCall/ffmpeg")
    again = Settings(
        port=8000,
        data_dir=settings.data_dir,
        models_dir=settings.models_dir,
        ollama_url=settings.ollama_url,
    )
    assert again.ffmpeg == Path("/opt/PostCall/ffmpeg")


def assert_16khz_mono(wav: Path) -> None:
    with wave.open(str(wav)) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 16000)
        assert w.getnframes() > 0


@pytest.mark.skipif(shutil.which("afconvert") is None, reason="needs macOS afconvert")
@pytest.mark.parametrize("clip", CLIPS)
def test_real_afconvert(clip: str, tmp_path: Path) -> None:
    dest = tmp_path / "out.wav"
    AfconvertDecoder().to_wav(DATA / clip, dest)
    assert_16khz_mono(dest)
    assert wav_duration(dest) == pytest.approx(3.0, abs=0.3)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg on the PATH")
@pytest.mark.parametrize("clip", CLIPS)
def test_real_ffmpeg(clip: str, tmp_path: Path) -> None:
    dest = tmp_path / "out.wav"
    FfmpegDecoder().to_wav(DATA / clip, dest)
    assert_16khz_mono(dest)
    assert wav_duration(dest) == pytest.approx(3.0, abs=0.3)


def not_audio(tmp_path: Path, kind: str) -> Path:
    """A file the converters must refuse: bytes that are not media, or a video with no sound."""
    if kind == "junk":
        junk = tmp_path / "junk.mp3"
        junk.write_bytes(b"this is not audio" * 100)
        return junk
    return DATA / "video-only.mp4"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg on the PATH")
@pytest.mark.parametrize("kind", ["junk", "video without sound"])
def test_real_ffmpeg_refuses_a_file_without_audio(kind: str, tmp_path: Path) -> None:
    with pytest.raises(TranscriptionError) as raised:
        FfmpegDecoder().to_wav(not_audio(tmp_path, kind), tmp_path / "out.wav")
    assert raised.value.code == "decode_failed"


@pytest.mark.skipif(shutil.which("afconvert") is None, reason="needs macOS afconvert")
@pytest.mark.parametrize("kind", ["junk", "video without sound"])
def test_real_afconvert_refuses_a_file_without_audio(kind: str, tmp_path: Path) -> None:
    with pytest.raises(TranscriptionError) as raised:
        AfconvertDecoder().to_wav(not_audio(tmp_path, kind), tmp_path / "out.wav")
    assert raised.value.code == "decode_failed"
