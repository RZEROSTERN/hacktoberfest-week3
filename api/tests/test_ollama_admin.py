import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.catalog import ModelNameError, load_catalog, validate_model_name
from app.errors import Cancelled
from app.ollama import OllamaAdmin, OllamaError
from app.system import free_disk_bytes, total_ram_bytes


def lines(*items: dict[str, Any]) -> bytes:
    return ("\n".join(json.dumps(i) for i in items) + "\n").encode()


PULL_OK = lines(
    {"status": "pulling manifest"},
    {"status": "pulling aaaa", "digest": "sha256:aaaa", "total": 1000, "completed": 300},
    {"status": "pulling aaaa", "digest": "sha256:aaaa", "total": 1000, "completed": 1000},
    {"status": "pulling bbbb", "digest": "sha256:bbbb", "total": 60, "completed": 0},
    {"status": "verifying sha256 digest"},
    {"status": "writing manifest"},
    {"status": "success"},
)


def admin(handler: Any) -> OllamaAdmin:
    return OllamaAdmin("http://ollama.test/", transport=httpx.MockTransport(handler))


def pull(client: OllamaAdmin, cancel: threading.Event | None = None) -> list[tuple[int, int]]:
    seen: list[tuple[int, int]] = []
    client.pull("m:1b", lambda c, t: seen.append((c, t)), cancel or threading.Event())
    return seen


def test_list_installed_models_and_flag_cloud_ones() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [
            {"name": "gemma4:e4b", "size": 6583656505},
            {"name": "gemma4:cloud", "size": 0, "remote_host": "https://ollama.com:443"},
        ]})  # fmt: skip

    client = admin(handler)
    local, cloud = client.list_models()
    assert (local.name, local.size_bytes, local.remote_host) == ("gemma4:e4b", 6583656505, None)
    assert cloud.remote_host == "https://ollama.com:443"
    assert client.installed("gemma4:e4b") == local
    assert client.installed("gemma4:12b") is None


def test_a_name_without_a_tag_means_latest() -> None:
    client = admin(
        lambda r: httpx.Response(200, json={"models": [{"name": "smollm2:latest", "size": 1}]})
    )
    assert client.installed("smollm2") is not None


def test_reachable_and_unreachable() -> None:
    assert admin(lambda r: httpx.Response(200, json={"models": []})).reachable()

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    assert not admin(down).reachable()
    with pytest.raises(OllamaError) as err:
        admin(down).list_models()
    assert err.value.code == "ollama_unreachable"


def test_delete() -> None:
    seen: list[Any] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(200)

    admin(handler).delete("smollm2:135m")
    assert seen == [("DELETE", "/api/delete", {"model": "smollm2:135m"})]
    with pytest.raises(OllamaError) as err:
        admin(lambda r: httpx.Response(404)).delete("nope")
    assert err.value.code == "model_not_found"


def test_pull_reports_bytes_summed_over_all_layers_and_ends_complete() -> None:
    request_bodies: list[Any] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_bodies.append(json.loads(request.content))
        return httpx.Response(200, content=PULL_OK)

    seen = pull(admin(handler))
    assert request_bodies == [{"model": "m:1b", "stream": True}]
    assert seen[0] == (300, 1000)
    assert [c for c, _ in seen] == sorted(c for c, _ in seen)  # never backwards
    assert seen[-2] == (1000, 1060)  # the second layer added to the total without lowering the bar
    assert seen[-1] == (1060, 1060)  # success means complete


def test_unknown_models_are_reported_by_ollama_before_any_download() -> None:
    body = lines(
        {"status": "pulling manifest"}, {"error": "pull model manifest: file does not exist"}
    )
    with pytest.raises(OllamaError) as err:
        pull(admin(lambda r: httpx.Response(200, content=body)))
    assert err.value.code == "model_not_found"


def test_malformed_names_are_refused_by_ollama_with_a_400() -> None:
    with pytest.raises(OllamaError) as err:
        pull(admin(lambda r: httpx.Response(400, json={"error": "invalid model name"})))
    assert err.value.code == "invalid_model_name"


@pytest.mark.parametrize(
    "message",
    [
        "Get https://registry.ollama.ai/v2/x: dial tcp: lookup registry.ollama.ai: no such host",
        "max retries exceeded: unexpected EOF",
        "read tcp 10.0.0.2:5555->1.2.3.4:443: connection reset by peer",
    ],
)
def test_network_trouble_between_ollama_and_the_registry_is_a_network_error(message: str) -> None:
    body = PULL_OK.split(b"\n")[1] + b"\n" + lines({"error": message})
    with pytest.raises(OllamaError) as err:
        pull(admin(lambda r: httpx.Response(200, content=body)))
    assert err.value.code == "network_error"


def test_an_error_nobody_recognises_is_a_generic_pull_failure() -> None:
    with pytest.raises(OllamaError) as err:
        pull(admin(lambda r: httpx.Response(200, content=lines({"error": "something odd"}))))
    assert err.value.code == "pull_failed"


class BrokenStream(httpx.SyncByteStream):
    """Sends the first lines of a pull and then the connection breaks."""

    def __iter__(self) -> Iterator[bytes]:
        yield PULL_OK.split(b"\n")[1] + b"\n"
        raise httpx.ReadError("connection broken")


def test_a_connection_that_breaks_mid_download_is_a_network_error() -> None:
    seen: list[tuple[int, int]] = []
    client = admin(lambda r: httpx.Response(200, stream=BrokenStream()))
    with pytest.raises(OllamaError) as err:
        client.pull("m:1b", lambda c, t: seen.append((c, t)), threading.Event())
    assert err.value.code == "network_error" and seen == [
        (300, 1000)
    ]  # progress up to the break was reported


def test_a_stream_that_just_stops_is_a_network_error() -> None:
    truncated = lines(
        {"status": "pulling manifest"}, {"digest": "sha256:aaaa", "total": 10, "completed": 5}
    )
    with pytest.raises(OllamaError) as err:
        pull(admin(lambda r: httpx.Response(200, content=truncated)))
    assert err.value.code == "network_error"


def test_pausing_stops_reading_the_stream() -> None:
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(Cancelled):
        pull(admin(lambda r: httpx.Response(200, content=PULL_OK)), cancel)


def test_ollama_not_running_while_pulling() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(OllamaError) as err:
        pull(admin(down))
    assert err.value.code == "ollama_unreachable"


# -- catalog and names --------------------------------------------------------------------------


def test_the_catalog_has_one_recommended_model_and_the_whisper_model() -> None:
    catalog = load_catalog()
    assert [m.model for m in catalog.llm if m.recommended] == ["gemma4:e4b"]
    assert (
        catalog.recommended.size_bytes == 6583656505 and catalog.recommended.license == "Apache 2.0"
    )
    assert catalog.whisper.file.endswith(".bin") and len(catalog.whisper.sha256) == 64
    assert "main" not in catalog.whisper.url.split("/")  # pinned to a revision, not a moving branch
    assert catalog.find("qwen3.5:9b") is not None and catalog.find("nope") is None


@pytest.mark.parametrize(
    "name", ["gemma4:e4b", "smollm2:135m", "user/model:q4", "hf.co/org/repo:Q4_K_M", "Qwen3.5:9B"]
)
def test_valid_model_names(name: str) -> None:
    assert validate_model_name(f"  {name} ") == name


@pytest.mark.parametrize(
    "name", ["", "bad name", "x;rm -rf", "a:b:c", "-start", "../etc", "x" * 201]
)
def test_invalid_model_names(name: str) -> None:
    with pytest.raises(ModelNameError) as err:
        validate_model_name(name)
    assert err.value.code == "invalid_model_name"


@pytest.mark.parametrize(
    "name", ["gemma4:cloud", "gpt-oss:120b-cloud", "qwen3-coder:480b-cloud", "Cloud:1b"]
)
def test_cloud_models_are_refused_because_they_would_send_calls_to_a_server(name: str) -> None:
    with pytest.raises(ModelNameError) as err:
        validate_model_name(name)
    assert err.value.code == "cloud_model"


def test_system_info(tmp_path: Path) -> None:  # noqa: F821
    assert total_ram_bytes() > 1 << 30
    assert (
        free_disk_bytes(tmp_path / "does" / "not" / "exist") > 0
    )  # uses the nearest existing folder
