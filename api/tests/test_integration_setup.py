"""The setup against the real Ollama: interrupt a real download, resume it, and run real checks.

Opt-in (`make test-setup`): it pulls a tiny model (about 270 MB) and loads the recommended model for
the compatibility check. The Whisper download is skipped here with a stand-in file; the real one was
verified once by hand against Hugging Face (size and SHA-256 match the catalog).
"""

import contextlib
import os
import socket
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.fakes import FakeDecoder, FakeTranscriber, wait_until

OLLAMA = os.environ.get("SCOPEWISE_OLLAMA_URL", "")
TINY = os.environ.get("SCOPEWISE_SETUP_TEST_MODEL", "smollm2:135m")
GOOD = os.environ.get("SCOPEWISE_LLM_MODEL", "")


def ollama_up() -> bool:
    try:
        return httpx.get(f"{OLLAMA}/api/tags", timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("SCOPEWISE_RUN_SETUP_TESTS") != "1" or not OLLAMA or not ollama_up(),
        reason="opt-in: needs SCOPEWISE_RUN_SETUP_TESTS=1 and a running Ollama (make test-setup)",
    ),
]


class CuttableProxy:
    """A TCP forwarder in front of Ollama whose connections can be cut, like a network drop."""

    def __init__(self, target: str) -> None:
        parsed = urlparse(target)
        self._target = (parsed.hostname or "127.0.0.1", parsed.port or 80)
        self._listener = socket.socket()
        self._listener.bind(("127.0.0.1", 0))
        self._listener.listen()
        self.url = f"http://127.0.0.1:{self._listener.getsockname()[1]}"
        self._connections: list[socket.socket] = []
        self._open = True
        threading.Thread(target=self._accept, daemon=True).start()

    def _accept(self) -> None:
        while self._open:
            try:
                client, _ = self._listener.accept()
            except OSError:
                return
            upstream = socket.create_connection(self._target)
            self._connections += [client, upstream]
            threading.Thread(target=self._pump, args=(client, upstream), daemon=True).start()
            threading.Thread(target=self._pump, args=(upstream, client), daemon=True).start()

    @staticmethod
    def _pump(source: socket.socket, sink: socket.socket) -> None:
        with contextlib.suppress(OSError):
            while data := source.recv(65536):
                sink.sendall(data)
        for sock in (source, sink):
            with contextlib.suppress(OSError):
                sock.shutdown(socket.SHUT_RDWR)

    def cut(self) -> None:
        for sock in self._connections:
            with contextlib.suppress(OSError):
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
        self._connections.clear()

    def close(self) -> None:
        self._open = False
        self.cut()
        self._listener.close()


@pytest.fixture
def proxy() -> Iterator[CuttableProxy]:
    p = CuttableProxy(OLLAMA)
    yield p
    p.close()


def real_client(tmp_path: Path, ollama_url: str) -> TestClient:
    # llm_model=None: the variable that seeds a development model must not apply here.
    stand_in = tmp_path / "stand-in.bin"
    stand_in.write_bytes(b"not a real model: the speech download is skipped in this test")
    settings = Settings(
        port=8000,
        data_dir=tmp_path / "data",
        models_dir=tmp_path / "models",
        ollama_url=ollama_url,
        whisper_model=stand_in,
        llm_model=None,
    )
    return TestClient(create_app(settings, transcriber=FakeTranscriber(), decoder=FakeDecoder()))


def progress(client: TestClient) -> dict[str, Any]:
    result: dict[str, Any] = client.get("/setup/progress").json()
    return result


def remove(model: str) -> None:
    httpx.request("DELETE", f"{OLLAMA}/api/delete", json={"model": model}, timeout=30)


def installed(model: str) -> bool:
    tags = httpx.get(f"{OLLAMA}/api/tags", timeout=10).json()["models"]
    return any(m["name"] == model for m in tags)


def test_a_real_download_cut_in_the_middle_resumes_and_ends_with_the_whole_model(
    tmp_path: Path, proxy: CuttableProxy
) -> None:
    remove(TINY)
    client = real_client(tmp_path, proxy.url)
    try:
        assert client.post("/setup/start", json={"model": TINY}).status_code == 202
        wait_until(
            lambda: (
                progress(client)["steps"][1]["total"] > 0
                and progress(client)["steps"][1]["completed"]
                >= 0.3 * progress(client)["steps"][1]["total"]
            ),
            timeout=60,
        )
        proxy.cut()  # the connection to the engine drops in the middle of the download

        wait_until(lambda: progress(client)["state"] in ("failed", "done"), timeout=30)
        failed = progress(client)
        assert failed["state"] == "failed" and failed["error_code"] == "network_error"
        assert "network connection was lost" in failed["error_message"]
        reached = failed["steps"][1]["completed"]
        assert 0 < reached < failed["steps"][1]["total"]
        assert not installed(TINY)
        fraction = failed["overall"]["fraction"]

        proxy_url_ok = real_client(tmp_path, OLLAMA)  # the "network" is back: a fresh connection
        client.close()
        client = proxy_url_ok
        restarted = progress(client)  # a new launch: the failed run is remembered, not restarted
        assert restarted["state"] == "failed" and restarted["steps"][1]["completed"] >= reached
        assert client.post("/setup/resume").status_code == 202
        wait_until(
            lambda: progress(client)["state"] in ("done", "compat_failed", "failed"), timeout=180
        )
        final = progress(client)
        assert final["state"] != "failed", final
        assert final["steps"][1]["state"] == "done" and installed(TINY)  # the whole model arrived
        assert final["overall"]["fraction"] >= fraction  # and the bar never went backwards
    finally:
        client.close()
        remove(TINY)


def test_a_model_too_small_for_the_task_fails_the_real_compatibility_check(tmp_path: Path) -> None:
    client = real_client(tmp_path, OLLAMA)
    try:
        client.post("/setup/start", json={"model": TINY})
        wait_until(
            lambda: progress(client)["state"] in ("done", "compat_failed", "failed"), timeout=180
        )
        final = progress(client)
        print(f"\n{TINY}: {final['state']} {final['error_code']}")
        assert final["state"] == "compat_failed", final
        assert final["error_code"].startswith("compat_")
        status = client.get("/setup/status").json()
        assert status["ready"] is False and status["llm"]["state"] == "not_selected"
    finally:
        client.close()
        remove(TINY)


@pytest.mark.skipif(
    not GOOD, reason="needs SCOPEWISE_LLM_MODEL (the recommended model, already installed)"
)
def test_the_recommended_model_passes_the_real_compatibility_check(tmp_path: Path) -> None:
    if not installed(GOOD):
        pytest.skip(f"{GOOD} is not installed")
    client = real_client(tmp_path, OLLAMA)
    try:
        client.post("/setup/start", json={"model": GOOD})
        wait_until(
            lambda: progress(client)["state"] in ("done", "compat_failed", "failed"), timeout=240
        )
        final = progress(client)
        assert final["state"] == "done", final
        steps = {s["id"]: s for s in final["steps"]}
        assert steps["llm"]["skipped"]  # it was already on the computer
        status = client.get("/setup/status").json()
        assert status["ready"] and status["llm"] == {"model": GOOD, "state": "ready"}
    finally:
        client.close()
