from fastapi.testclient import TestClient

from app.config import Settings


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_creates_data_and_models_dirs(client: TestClient, settings: Settings) -> None:
    assert settings.data_dir.is_dir()
    assert settings.models_dir.is_dir()


def test_binds_to_loopback_by_default(settings: Settings) -> None:
    assert settings.host == "127.0.0.1"


def test_cors_allows_configured_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
