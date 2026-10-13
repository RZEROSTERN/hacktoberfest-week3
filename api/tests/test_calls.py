import logging
import threading
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.config import Settings
from app.main import create_app
from app.models import Call, CallStatus
from tests.fakes import SEGMENTS, FakeDecoder, FakeTranscriber, wait_until

AUDIO = b"not really audio, the decoder is fake"


def upload(
    client: TestClient, name: str = "client-call.mp3", keep_audio: bool = False
) -> dict[str, Any]:
    response = client.post(
        "/calls",
        files={"file": (name, AUDIO, "audio/mpeg")},
        data={"keep_audio": "true" if keep_audio else "false"},
    )
    assert response.status_code == 202, response.text
    body: dict[str, Any] = response.json()
    return body


def status_of(client: TestClient, call_id: str) -> str:
    return str(client.get(f"/calls/{call_id}").json()["status"])


def wait_for_status(client: TestClient, call_id: str, status: str) -> None:
    wait_until(lambda: status_of(client, call_id) == status)


def audio_dir(settings: Settings, call_id: str) -> Path:
    return settings.data_dir / "audio" / call_id


def test_upload_transcribes_and_deletes_audio(client: TestClient, settings: Settings) -> None:
    call = upload(client)
    wait_for_status(client, call["id"], "done")

    detail = client.get(f"/calls/{call['id']}").json()
    assert detail["progress"] == 1.0
    assert detail["language"] == "es"
    assert detail["duration_s"] == pytest.approx(1.0)
    assert detail["audio_available"] is False
    assert not audio_dir(settings, call["id"]).exists()
    assert not (settings.data_dir / "tmp" / call["id"]).exists()

    transcript = client.get(f"/calls/{call['id']}/transcript").json()
    assert [s["id"] for s in transcript["segments"]] == [0, 1]
    assert transcript["segments"][1] == {
        "id": 1,
        "start": 3.5,
        "end": 9.0,
        "text": SEGMENTS[1].text,
    }
    assert transcript["language"] == "es"


def test_keep_audio_keeps_the_original(client: TestClient, settings: Settings) -> None:
    call = upload(client, keep_audio=True)
    wait_for_status(client, call["id"], "done")
    assert client.get(f"/calls/{call['id']}").json()["audio_available"] is True
    assert (audio_dir(settings, call["id"]) / "original.mp3").read_bytes() == AUDIO


def test_rejects_unsupported_and_empty_files(client: TestClient) -> None:
    bad_type = client.post("/calls", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert bad_type.status_code == 415
    empty = client.post("/calls", files={"file": ("call.mp3", b"", "audio/mpeg")})
    assert empty.status_code == 400
    assert client.get("/calls").json() == []


def test_user_supplied_file_name_never_becomes_a_path(
    client: TestClient, settings: Settings
) -> None:
    call = upload(client, name="../../etc/evil.mp3", keep_audio=True)
    assert call["title"] == "evil.mp3"
    wait_for_status(client, call["id"], "done")
    stored = list(settings.data_dir.rglob("original.mp3"))
    assert len(stored) == 1 and stored[0].parent == audio_dir(settings, call["id"])


def test_progress_is_reported_and_never_goes_backwards(
    client: TestClient, transcriber: FakeTranscriber
) -> None:
    transcriber.progress_steps = [0.25, 0.5, 0.3]
    transcriber.gate = threading.Event()
    call = upload(client)
    wait_until(lambda: client.get(f"/calls/{call['id']}").json()["progress"] >= 0.5)
    running = client.get(f"/calls/{call['id']}").json()
    assert running["status"] == "transcribing"
    assert running["progress"] == pytest.approx(0.5)
    transcriber.gate.set()
    wait_for_status(client, call["id"], "done")


def test_cancel_stops_the_job_and_removes_the_audio(
    client: TestClient, transcriber: FakeTranscriber, settings: Settings
) -> None:
    transcriber.gate = threading.Event()
    call = upload(client)
    wait_for_status(client, call["id"], "transcribing")
    assert client.post(f"/calls/{call['id']}/cancel").status_code == 200
    wait_for_status(client, call["id"], "cancelled")
    assert not audio_dir(settings, call["id"]).exists()
    assert client.get(f"/calls/{call['id']}/transcript").status_code == 409
    assert client.post(f"/calls/{call['id']}/cancel").status_code == 409  # nothing left to cancel


def test_failure_keeps_the_audio_and_can_be_retried(
    client: TestClient, transcriber: FakeTranscriber, settings: Settings
) -> None:
    transcriber.fail_with = "model_missing"
    call = upload(client)
    wait_for_status(client, call["id"], "failed")
    failed = client.get(f"/calls/{call['id']}").json()
    assert failed["error_code"] == "model_missing"
    assert "speech model" in failed["error_message"]
    assert failed["audio_available"] is True

    transcriber.fail_with = None
    assert client.post(f"/calls/{call['id']}/retry").status_code == 202
    wait_for_status(client, call["id"], "done")
    after = client.get(f"/calls/{call['id']}").json()
    assert after["error_code"] is None
    assert not audio_dir(settings, call["id"]).exists()  # deleted once the retry succeeded


def test_retry_only_applies_to_failed_calls(client: TestClient) -> None:
    call = upload(client)
    wait_for_status(client, call["id"], "done")
    assert client.post(f"/calls/{call['id']}/retry").status_code == 409


def test_delete_removes_everything(client: TestClient, settings: Settings) -> None:
    call = upload(client, keep_audio=True)
    wait_for_status(client, call["id"], "done")
    assert client.delete(f"/calls/{call['id']}").status_code == 204
    assert client.get(f"/calls/{call['id']}").status_code == 404
    assert not audio_dir(settings, call["id"]).exists()


def test_cannot_delete_a_running_job(client: TestClient, transcriber: FakeTranscriber) -> None:
    transcriber.gate = threading.Event()
    call = upload(client)
    wait_for_status(client, call["id"], "transcribing")
    assert client.delete(f"/calls/{call['id']}").status_code == 409
    transcriber.gate.set()
    wait_for_status(client, call["id"], "done")


def test_unknown_call_and_unready_transcript(
    client: TestClient, transcriber: FakeTranscriber
) -> None:
    assert client.get("/calls/nope").status_code == 404
    transcriber.gate = threading.Event()
    call = upload(client)
    assert client.get(f"/calls/{call['id']}/transcript").status_code == 409
    transcriber.gate.set()
    wait_for_status(client, call["id"], "done")


def test_list_is_newest_first(client: TestClient) -> None:
    first = upload(client, name="a.mp3")
    wait_for_status(client, first["id"], "done")
    second = upload(client, name="b.mp3")
    wait_for_status(client, second["id"], "done")
    assert [c["id"] for c in client.get("/calls").json()] == [second["id"], first["id"]]


def test_jobs_left_running_are_marked_interrupted_on_start(settings: Settings) -> None:
    first = create_app(settings, transcriber=FakeTranscriber(), decoder=FakeDecoder())
    with Session(first.state.engine) as session:
        session.add(Call(id="abc", title="x.mp3", audio_ext=".mp3", status=CallStatus.TRANSCRIBING))
        session.commit()
    audio = settings.data_dir / "audio" / "abc"
    audio.mkdir(parents=True)
    (audio / "original.mp3").write_bytes(AUDIO)

    restarted = TestClient(
        create_app(settings, transcriber=FakeTranscriber(), decoder=FakeDecoder())
    )
    call = restarted.get("/calls/abc").json()
    assert call["status"] == "failed"
    assert call["error_code"] == "interrupted"
    assert call["audio_available"] is True  # still retryable


def test_logs_never_contain_file_names_or_transcript_text(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        call = upload(client, name="secret-client-acme.mp3")
        wait_for_status(client, call["id"], "done")
        client.get(f"/calls/{call['id']}/transcript")
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "secret-client-acme" not in logged
    assert SEGMENTS[0].text not in logged
