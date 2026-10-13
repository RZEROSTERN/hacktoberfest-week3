"""Entrypoint shared by `make dev-api` and the packaged binary."""

import uvicorn

from app.config import Settings
from app.main import create_app


def main() -> None:
    settings = Settings()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
