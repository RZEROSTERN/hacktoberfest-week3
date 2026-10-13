from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


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
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))
