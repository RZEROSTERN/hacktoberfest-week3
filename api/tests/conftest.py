from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.fake_llm import PROFILE, ScriptedLLM
from tests.fakes import FakeDecoder, FakeTranscriber
from tests.helpers import add_done_call, app_of


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        port=8000,
        data_dir=tmp_path / "data",
        models_dir=tmp_path / "models",
        ollama_url="http://127.0.0.1:1",
        cors_origins=["http://localhost:3000"],
    )


@pytest.fixture
def transcriber() -> FakeTranscriber:
    return FakeTranscriber()


@pytest.fixture
def llm() -> ScriptedLLM:
    return ScriptedLLM([])


@pytest.fixture
def client(settings: Settings, transcriber: FakeTranscriber, llm: ScriptedLLM) -> TestClient:
    return TestClient(create_app(settings, transcriber=transcriber, decoder=FakeDecoder(), llm=llm))


@pytest.fixture
def ready(client: TestClient) -> TestClient:
    """A finished call and a saved profile."""
    add_done_call(app_of(client))
    assert client.put("/profile", json=PROFILE).status_code == 200
    return client
