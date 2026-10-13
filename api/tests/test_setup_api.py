import json
import os
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import setup as setup_steps
from app.catalog import Catalog, load_catalog
from app.compat import CompatError
from app.config import Settings
from app.downloads import WhisperDownloader
from app.main import create_app
from app.models import SetupRun, SetupState
from app.settings_store import LLM_MODEL, get_setting
from tests.fake_ollama import FakeOllama
from tests.fakes import FakeDecoder, FakeTranscriber, wait_until
from tests.range_server import RangeServer
from tests.test_downloads import model_for

DATA = os.urandom(2 * 1024 * 1024 + 7)
GIB = 2**30
TERMINAL = {"paused", "failed", "compat_failed", "interrupted", "done"}


class FakeCompat:
    def __init__(self) -> None:
        self.error: CompatError | None = None
        self.checked: list[str] = []

    def check(self, model: str, cancel: threading.Event) -> None:
        self.checked.append(model)
        if self.error is not None:
            raise self.error


class Rig:
    """A running app wired to a fake engine, a local download server and a fake model check."""

    def __init__(
        self, tmp_path: Path, server: RangeServer, ollama: FakeOllama, compat: FakeCompat
    ) -> None:
        self.tmp_path, self.server, self.ollama, self.compat = tmp_path, server, ollama, compat
        self.catalog: Catalog = load_catalog().model_copy(update={"whisper": model_for(server)})
        self.settings = Settings(
            port=8000,
            data_dir=tmp_path / "data",
            models_dir=tmp_path / "models",
            ollama_url="http://127.0.0.1:1",
        )
        self.client = self.new_client()

    def new_client(self, settings: Settings | None = None) -> TestClient:
        app = create_app(
            settings or self.settings,
            transcriber=FakeTranscriber(),
            decoder=FakeDecoder(),
            catalog=self.catalog,
            ollama=self.ollama,
            whisper=WhisperDownloader(self.catalog.whisper, (settings or self.settings).models_dir),
            compat=self.compat,
        )
        return TestClient(app)

    def start(self, model: str = "gemma4:e4b") -> Any:
        return self.client.post("/setup/start", json={"model": model})

    def progress(self) -> dict[str, Any]:
        result: dict[str, Any] = self.client.get("/setup/progress").json()
        return result

    def wait(self, *states: str) -> dict[str, Any]:
        wait_until(lambda: self.progress()["state"] in (states or TERMINAL), timeout=20)
        return self.progress()

    def status(self) -> dict[str, Any]:
        result: dict[str, Any] = self.client.get("/setup/status").json()
        return result


@pytest.fixture
def server() -> Iterator[RangeServer]:
    with RangeServer(DATA) as running:
        yield running


@pytest.fixture
def rig(tmp_path: Path, server: RangeServer) -> Rig:
    return Rig(tmp_path, server, FakeOllama(), FakeCompat())


def step_states(progress: dict[str, Any]) -> dict[str, str]:
    return {s["id"]: s["state"] for s in progress["steps"]}


# -- what the first-launch screen shows ------------------------------------------------------


def test_the_model_list_is_the_tested_one_with_sizes_licenses_and_notes(rig: Rig) -> None:
    data = rig.client.get("/setup/recommended").json()
    assert [m["model"] for m in data["llm"]][:1] == ["gemma4:e4b"]
    best = data["llm"][0]
    assert (
        best["recommended"] and best["license"] == "Apache 2.0" and best["size_bytes"] == 6583656505
    )
    assert best["note"] and not any(m["recommended"] for m in data["llm"][1:])
    assert data["whisper"]["state"] == "missing" and data["whisper"]["size_bytes"] == len(DATA)
    assert data["library_url"] == "https://ollama.com/library" and data["margin_bytes"] > 0


@pytest.mark.parametrize(
    ("ram_gb", "flagged"),
    [
        (16, ["gemma4:12b"]),
        (8, ["qwen3.5:9b", "mistral-nemo:12b", "gemma4:12b"]),
        (32, []),
        (4, ["gemma4:e4b", "qwen3.5:9b", "qwen3.5:4b", "mistral-nemo:12b", "gemma4:12b"]),
    ],
)
def test_models_that_need_more_memory_than_this_computer_has_are_flagged(
    rig: Rig, monkeypatch: pytest.MonkeyPatch, ram_gb: int, flagged: list[str]
) -> None:
    monkeypatch.setattr("app.routes_setup.total_ram_bytes", lambda: ram_gb * GIB)
    data = rig.client.get("/setup/recommended").json()
    assert [m["model"] for m in data["llm"] if m["not_recommended_for_this_computer"]] == flagged
    assert data["system"]["total_ram_bytes"] == ram_gb * GIB


def test_system_info_and_installed_models_are_reported(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.routes_setup.free_disk_bytes", lambda path: 123 * GIB)
    rig.ollama.add("qwen3.5:4b")
    assert rig.client.get("/system").json()["free_disk_bytes"] == 123 * GIB
    llm = {m["model"]: m for m in rig.client.get("/setup/recommended").json()["llm"]}
    assert llm["qwen3.5:4b"]["installed"] and not llm["gemma4:e4b"]["installed"]


def test_nothing_is_ready_on_a_first_launch(rig: Rig) -> None:
    status = rig.status()
    assert status["ready"] is False and status["problem"] is None
    assert status["llm"] == {"model": None, "state": "not_selected"}
    assert status["whisper"]["state"] == "missing" and status["compat_ok"] is False
    progress = rig.progress()
    assert progress["state"] == "idle" and set(step_states(progress).values()) == {"pending"}
    assert [s["id"] for s in progress["steps"]] == [
        "engine",
        "llm",
        "whisper",
        "verify",
        "compat",
        "ready",
    ]


def test_an_engine_that_is_not_running_is_a_problem_not_a_setup_request(rig: Rig) -> None:
    rig.ollama.up = False
    status = rig.status()
    assert status["problem"] == "ollama_unreachable" and "not running" in status["problem_message"]
    assert status["ready"] is False and status["ollama_reachable"] is False


# -- a complete run --------------------------------------------------------------------------


def test_a_full_setup_goes_through_all_six_steps_and_ends_ready(rig: Rig) -> None:
    assert rig.start().status_code == 202
    progress = rig.wait()
    assert progress["state"] == "done" and progress["error_code"] is None
    assert set(step_states(progress).values()) == {"done"}
    assert [s["label"] for s in progress["steps"]][1] == "Downloading the language model"
    assert progress["overall"]["fraction"] == 1.0

    assert rig.ollama.pulled == ["gemma4:e4b"]
    assert WhisperDownloader(
        rig.catalog.whisper, rig.settings.models_dir
    ).verify()  # real file, real checksum
    assert rig.compat.checked == ["gemma4:e4b"]
    status = rig.status()
    assert status["ready"] and status["llm"] == {"model": "gemma4:e4b", "state": "ready"}
    assert status["whisper"]["state"] == "ready" and status["compat_ok"] is True
    assert get_setting(rig.client.app.state.engine, LLM_MODEL) == "gemma4:e4b"  # type: ignore[attr-defined]


def test_the_downloads_report_bytes_speed_and_time_left(rig: Rig) -> None:
    rig.ollama.gate = threading.Event()
    rig.start()
    wait_until(lambda: rig.progress()["steps"][1]["completed"] >= 100)
    llm = rig.progress()["steps"][1]
    assert llm["state"] == "running" and llm["detail"] == "gemma4:e4b"
    assert llm["total"] > 0 and 0 < llm["completed"] <= llm["total"]
    assert rig.progress()["overall"]["total_bytes"] > 0
    rig.ollama.gate.set()
    rig.wait("done")


def test_a_model_already_on_the_computer_skips_the_downloads(rig: Rig) -> None:
    rig.start()
    rig.wait("done")
    rig.ollama.add("qwen3.5:4b", 5)
    rig.ollama.pulled.clear()
    rig.start("qwen3.5:4b")
    progress = rig.wait("done")
    steps = {s["id"]: s for s in progress["steps"]}
    assert steps["llm"]["skipped"] and steps["whisper"]["skipped"]
    assert rig.ollama.pulled == [] and rig.compat.checked[-1] == "qwen3.5:4b"
    assert get_setting(rig.client.app.state.engine, LLM_MODEL) == "qwen3.5:4b"  # type: ignore[attr-defined]


def test_the_speech_model_override_for_development_counts_as_downloaded(
    rig: Rig, tmp_path: Path
) -> None:
    override = tmp_path / "ggml-test.bin"
    override.write_bytes(b"x")
    client = rig.new_client(rig.settings.model_copy(update={"whisper_model": override}))
    rig.client = client
    rig.start()
    progress = rig.wait("done")
    assert {s["id"]: s["skipped"] for s in progress["steps"]}["whisper"] is True
    assert rig.server.requests == []  # nothing was downloaded


# -- names -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("bad name!", "not a valid model name"),
        ("gemma4:cloud", "send your calls to a server"),
        ("", None),
    ],
)
def test_bad_names_are_refused_before_anything_starts(
    rig: Rig, name: str, text: str | None
) -> None:
    response = rig.start(name)
    assert response.status_code == 422
    if text:
        assert text in response.json()["detail"]
    assert rig.progress()["state"] == "idle" and rig.ollama.pulled == []


def test_a_model_that_does_not_exist_is_reported_by_the_engine(rig: Rig) -> None:
    rig.ollama.fail_after, rig.ollama.fail_with = 1, "model_not_found"
    rig.start("no-such-model:1b")
    progress = rig.wait()
    assert progress["state"] == "failed" and progress["error_code"] == "model_not_found"
    assert "No model with that name" in progress["error_message"]


def test_a_cloud_model_that_slips_through_is_removed_and_never_used(rig: Rig) -> None:
    rig.ollama.remote_host = "https://ollama.com:443"
    rig.start("sneaky:1b")
    progress = rig.wait()
    assert progress["state"] == "failed" and progress["error_code"] == "cloud_model"
    assert rig.ollama.deleted == ["sneaky:1b"] and rig.compat.checked == []
    assert get_setting(rig.client.app.state.engine, LLM_MODEL) is None  # type: ignore[attr-defined]


# -- interruptions ---------------------------------------------------------------------------


def test_a_network_drop_during_the_language_model_download_can_be_retried(rig: Rig) -> None:
    rig.ollama.fail_after = 2
    rig.start()
    failed = rig.wait()
    assert failed["state"] == "failed" and failed["error_code"] == "network_error"
    assert "network connection was lost" in failed["error_message"]
    assert step_states(failed)["llm"] == "failed"
    assert failed["steps"][1]["completed"] == 600
    before = failed["overall"]["fraction"]

    assert rig.client.post("/setup/resume").status_code == 202
    done = rig.wait()
    assert done["state"] == "done"
    assert done["overall"]["fraction"] >= before  # the bar never went backwards


def test_a_network_drop_during_the_speech_model_download_resumes_with_a_range_request(
    rig: Rig,
) -> None:
    rig.server.drop_after = 1_000_000
    rig.start()
    failed = rig.wait()
    assert failed["state"] == "failed" and failed["error_code"] == "network_error"
    assert step_states(failed)["whisper"] == "failed" and step_states(failed)["llm"] == "done"
    assert rig.status()["whisper"]["state"] == "partial"

    rig.client.post("/setup/resume")
    assert rig.wait()["state"] == "done"
    assert rig.server.requests[-1] is not None and rig.server.requests[-1].startswith("bytes=")
    assert rig.status()["ready"]


def test_pausing_and_resuming(rig: Rig) -> None:
    rig.ollama.gate = threading.Event()
    rig.start()
    wait_until(lambda: rig.progress()["steps"][1]["completed"] >= 100)
    assert rig.client.post("/setup/pause").status_code == 200
    paused = rig.wait()
    assert paused["state"] == "paused"
    assert rig.status()["llm"]["state"] == "partial"
    rig.ollama.gate.set()
    rig.client.post("/setup/resume")
    assert rig.wait()["state"] == "done"


def test_a_run_cut_short_by_closing_the_app_is_offered_again_not_resumed_silently(
    rig: Rig, tmp_path: Path
) -> None:
    rig.ollama.gate = threading.Event()
    with rig.client:  # leaving the block shuts the app down, like quitting it
        rig.start()
        wait_until(lambda: rig.progress()["steps"][1]["completed"] >= 100)
    # the next launch
    rig.ollama.gate = None
    rig.client = rig.new_client()
    status = rig.status()
    assert status["run"]["state"] == "interrupted" and status["llm"]["state"] == "partial"
    assert status["ready"] is False
    assert rig.progress()["state"] == "interrupted" and rig.ollama.pulled == [
        "gemma4:e4b"
    ]  # nothing restarted
    assert rig.progress()["steps"][1]["completed"] >= 100  # what was done is remembered

    assert rig.client.post("/setup/resume").status_code == 202  # only after the user says yes
    assert rig.wait()["state"] == "done"


def test_a_killed_app_leaves_a_running_run_that_is_marked_interrupted(rig: Rig) -> None:
    with Session(rig.client.app.state.engine) as session:  # type: ignore[attr-defined]
        session.add(
            SetupRun(id=1, state=SetupState.RUNNING, llm_model="gemma4:e4b", overall_fraction=0.4)
        )
        session.commit()
    restarted = rig.new_client()
    assert restarted.get("/setup/progress").json()["state"] == "interrupted"
    assert restarted.get("/setup/progress").json()["overall"]["fraction"] == pytest.approx(0.4)


def test_there_is_nothing_to_resume_at_first(rig: Rig) -> None:
    assert rig.client.post("/setup/resume").status_code == 409


def test_only_one_setup_runs_at_a_time(rig: Rig) -> None:
    rig.ollama.gate = threading.Event()
    rig.start()
    assert rig.start("qwen3.5:4b").status_code == 409
    rig.ollama.gate.set()
    rig.wait("done")


# -- disk space ------------------------------------------------------------------------------


def test_there_must_be_room_for_the_downloads_before_they_start(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        setup_steps, "free_disk_bytes", lambda path: 2 * GIB
    )  # the model alone is 6.6 GB
    rig.start()
    progress = rig.wait()
    assert progress["state"] == "failed" and progress["error_code"] == "not_enough_disk"
    assert "not enough free disk space" in progress["error_message"]
    assert rig.ollama.pulled == [] and rig.server.requests == []  # nothing was downloaded


def test_a_model_outside_the_catalog_is_checked_for_room_as_soon_as_its_size_is_known(
    rig: Rig, monkeypatch: pytest.MonkeyPatch
) -> None:
    rig.ollama.steps = [(0, 50 * GIB), (10, 50 * GIB)]
    monkeypatch.setattr(setup_steps, "free_disk_bytes", lambda path: 20 * GIB)
    rig.start("someone/huge-model:70b")
    progress = rig.wait()
    assert progress["state"] == "failed" and progress["error_code"] == "not_enough_disk"
    assert rig.server.requests == []


# -- the compatibility check -----------------------------------------------------------------


def test_a_model_that_fails_the_check_is_not_activated_and_the_user_can_pick_another(
    rig: Rig,
) -> None:
    rig.start()
    rig.wait("done")  # a working model is already in use
    rig.compat.error = CompatError("compat_not_enough")
    rig.start("qwen3.5:4b")
    progress = rig.wait()
    assert progress["state"] == "compat_failed" and progress["error_code"] == "compat_not_enough"
    assert "too small" in progress["error_message"]
    assert step_states(progress)["compat"] == "failed" and step_states(progress)["llm"] == "done"
    assert get_setting(rig.client.app.state.engine, LLM_MODEL) == "gemma4:e4b"  # type: ignore[attr-defined]
    assert rig.status()["compat_ok"] is True and rig.status()["llm"]["model"] == "gemma4:e4b"

    rig.compat.error = None  # the user chooses the recommended model instead
    rig.start("gemma4:e4b")
    assert rig.wait()["state"] == "done"


def test_a_first_model_that_fails_leaves_the_app_needing_setup(rig: Rig) -> None:
    rig.compat.error = CompatError("compat_invalid_output")
    rig.start("qwen3.5:4b")
    assert rig.wait()["state"] == "compat_failed"
    status = rig.status()
    assert status["ready"] is False and status["llm"]["state"] == "not_selected"
    assert status["whisper"]["state"] == "ready"  # the speech model is kept: no second download
    offered = rig.client.get("/setup/recommended").json()["llm"]
    assert [m["model"] for m in offered if m["recommended"]] == ["gemma4:e4b"]  # the way out


# -- progress stream -------------------------------------------------------------------------


def test_the_progress_stream_sends_events_until_the_run_ends(rig: Rig) -> None:
    rig.start()
    events: list[dict[str, Any]] = []
    with rig.client.stream("GET", "/setup/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line.removeprefix("data: ")))
    assert events and events[-1]["state"] == "done"
    fractions = [e["overall"]["fraction"] for e in events]
    assert fractions == sorted(fractions)  # never backwards


def test_the_stream_of_a_finished_run_sends_one_event_and_closes(rig: Rig) -> None:
    rig.start()
    rig.wait("done")
    with rig.client.stream("GET", "/setup/events") as response:
        data = [line for line in response.iter_lines() if line.startswith("data: ")]
    assert len(data) == 1


# -- managing the models in Settings ---------------------------------------------------------


def test_listing_switching_and_deleting_models(rig: Rig) -> None:
    rig.start()
    rig.wait("done")
    rig.ollama.add("qwen3.5:4b", 5)
    models = rig.client.get("/models").json()
    assert models["active_model"] == "gemma4:e4b" and models["whisper"]["state"] == "ready"
    by_name = {m["name"]: m for m in models["llm"]}
    best = by_name["gemma4:e4b"]
    assert (
        best["active"]
        and best["compat_ok"]
        and best["recommended"]
        and best["title"] == "Gemma 4 E4B"
    )
    assert not by_name["qwen3.5:4b"]["compat_ok"]  # never checked on this computer

    activate = "/models/llm/activate"
    assert (
        rig.client.post(activate, json={"model": "qwen3.5:4b"}).status_code == 409
    )  # check it first
    rig.start("qwen3.5:4b")  # nothing to download: it only runs the check and switches
    rig.wait("done")
    assert rig.client.get("/models").json()["active_model"] == "qwen3.5:4b"

    assert (
        rig.client.post(activate, json={"model": "gemma4:e4b"}).status_code == 200
    )  # checked before
    assert rig.client.delete("/models/llm/gemma4:e4b").status_code == 409  # now in use
    assert rig.client.post(activate, json={"model": "qwen3.5:4b"}).status_code == 200
    assert rig.client.delete("/models/llm/gemma4:e4b").status_code == 204
    assert rig.ollama.deleted == ["gemma4:e4b"]
    assert rig.client.delete("/models/llm/qwen3.5:4b").status_code == 409  # the one in use stays
    assert rig.client.delete("/models/llm/nope:1b").status_code == 404


def test_deleting_the_speech_model_sends_the_app_back_to_setup(rig: Rig) -> None:
    rig.start()
    rig.wait("done")
    assert rig.status()["ready"]
    assert rig.client.delete("/models/whisper").status_code == 204
    status = rig.status()
    assert status["ready"] is False and status["whisper"]["state"] == "missing"


def test_models_cannot_be_deleted_while_a_download_runs(rig: Rig) -> None:
    rig.ollama.gate = threading.Event()
    rig.start()
    assert rig.client.delete("/models/whisper").status_code == 409
    rig.ollama.gate.set()
    rig.wait("done")
