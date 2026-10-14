"""Entrypoint shared by `make dev-api` and the packaged binary."""

import os
import signal

import uvicorn

from app.config import Settings
from app.lifecycle import watch_parent
from app.main import create_app


def main() -> None:
    settings = Settings()
    if settings.parent_pid is not None:
        # SIGTERM lets uvicorn shut down cleanly, which stops any running transcription.
        watch_parent(settings.parent_pid, lambda: os.kill(os.getpid(), signal.SIGTERM))
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
