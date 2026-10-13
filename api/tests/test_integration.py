"""Runs the real engines (macOS afconvert + whisper.cpp) on a 20-second clip of the sample call.

Skipped unless SCOPEWISE_WHISPER_CLI and SCOPEWISE_TEST_WHISPER_MODEL point at files. Use a small
model (base) here: the tests only need to prove the pipeline works end to end.
"""

import os
import subprocess
import sys
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.fakes import wait_until

CLI = os.environ.get("SCOPEWISE_WHISPER_CLI", "")
MODEL = os.environ.get("SCOPEWISE_TEST_WHISPER_MODEL", "")
SAMPLE = Path(__file__).resolve().parents[2] / "samples" / "interview.mp3"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        sys.platform != "darwin"
        or not Path(CLI).is_file()
        or not Path(MODEL).is_file()
        or not SAMPLE.is_file(),
        reason="needs macOS, SCOPEWISE_WHISPER_CLI, SCOPEWISE_TEST_WHISPER_MODEL and the sample",
    ),
]

# How afconvert writes each container (it cannot encode mp3; the sample itself is an mp3).
FORMATS: dict[str, list[str]] = {
    "wav": [],
    "m4a": ["-f", "m4af", "-d", "aac"],
    "mp4": ["-f", "mp4f", "-d", "aac"],
}


@pytest.fixture(scope="module")
def clip_wav(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("clip")
    full = folder / "full.wav"
    subprocess.run(
        ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(SAMPLE), str(full)],
        check=True,
    )
    clip = folder / "clip.wav"
    with wave.open(str(full)) as src, wave.open(str(clip), "wb") as dst:
        dst.setparams(src.getparams())
        dst.writeframes(src.readframes(16000 * 20))
    return clip


@pytest.fixture
def real_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        port=8000,
        data_dir=tmp_path / "data",
        models_dir=tmp_path / "models",
        ollama_url="http://127.0.0.1:1",
        whisper_cli=Path(CLI),
        whisper_model=Path(MODEL),
        whisper_threads=2,
    )
    return TestClient(create_app(settings))  # real decoder and transcriber


@pytest.mark.parametrize("fmt", list(FORMATS))
def test_real_pipeline(fmt: str, clip_wav: Path, real_client: TestClient, tmp_path: Path) -> None:
    source = clip_wav
    if FORMATS[fmt]:
        source = tmp_path / f"clip.{fmt}"
        subprocess.run(["afconvert", *FORMATS[fmt], str(clip_wav), str(source)], check=True)
    response = real_client.post("/calls", files={"file": (f"clip.{fmt}", source.read_bytes())})
    assert response.status_code == 202
    call_id = response.json()["id"]

    wait_until(
        lambda: real_client.get(f"/calls/{call_id}").json()["status"] in ("done", "failed"),
        timeout=180,
    )
    call = real_client.get(f"/calls/{call_id}").json()
    assert call["status"] == "done", call
    assert call["language"] == "es"
    assert call["duration_s"] == pytest.approx(20.0, abs=0.5)

    segments = real_client.get(f"/calls/{call_id}/transcript").json()["segments"]
    assert segments and all(s["end"] > s["start"] for s in segments)
    text = " ".join(s["text"] for s in segments).lower()
    assert any(word in text for word in ("entrevista", "sistema", "negocio")), text
    assert not list((tmp_path / "data").rglob("original.*"))  # audio deleted after transcription
