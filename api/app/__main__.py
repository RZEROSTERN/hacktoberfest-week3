"""Entrypoint shared by `make dev-api` and the packaged binary."""

import uvicorn

from app.config import Settings
from app.lifecycle import watch_parent
from app.main import create_app


def build_server(settings: Settings) -> uvicorn.Server:
    config = uvicorn.Config(create_app(settings), host=settings.host, port=settings.port)
    return uvicorn.Server(config)


def request_shutdown(server: uvicorn.Server) -> None:
    """Ask uvicorn to stop cleanly, which also stops any running transcription.

    Not a signal sent to ourselves: on Windows that ends the process abruptly instead of letting
    uvicorn shut down.
    """
    server.should_exit = True


def main() -> None:
    settings = Settings()
    server = build_server(settings)
    if settings.parent_pid is not None:
        watch_parent(settings.parent_pid, lambda: request_shutdown(server))
    server.run()


if __name__ == "__main__":
    main()
